# routers/auth.py
import os
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_db
from crud.admin import create_admin_log, count_admin_stage1_attempts_last_24h
from crud.auth import is_admin_login_enabled, invalidate_previous_sessions, create_login_history
from crud.user import (
    get_user_by_phone, create_user, create_user_status,
    get_valid_invite_code, delete_invite_code
)
from schemas.admin import AdminSecondVerifyRequest, AdminSecondVerifyResponseData
from schemas.user import UserCreate, UserLogin, Token
from utills.email_utils import send_admin_login_alert
from utills.geo_utils import get_city_from_ip
from utills.ip_utils import get_client_ip
from utills.response import success_response
from utills.security import verify_password, create_access_token, create_access_token_with_jti
from models import AdminLog, LoginHistory
from utills.logging_conf import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["认证"])

# 环境变量
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "00000000000")
# 使用一个占位哈希，确保永远不会匹配真实密码（这里用空字符串的 bcrypt hash）
ADMIN_1ST_PWD_HASH = os.getenv(
    "ADMIN_1ST_PWD",
    "$2b$12$abcdefghijklmnopqrstuvwxyz1234567890123456789012345678901"  # 无效哈希
)
ADMIN_2ND_PWD_HASH = os.getenv(
    "ADMIN_2ND_PWD",
    "$2b$12$zyxwvutsrqponmlkjihgfedcba9876543210987654321098765432109"  # 无效哈希
)

# 内存存储待二级验证的管理员会话： phone -> expire_timestamp
pending_admin_verifications = {}
PENDING_EXPIRE_SECONDS = 30  # 30秒内必须完成二级验证


@router.post("/register", summary="用户注册")
async def register(user_data: UserCreate, request: Request, db: AsyncSession = Depends(get_db)):
    """
    注册流程：
    1. 校验手机号是否已被注册
    2. 校验邀请码是否存在且未过期
    3. 创建用户（密码加密） + 创建默认五维状态
    4. 删除已使用的邀请码（一次性）
    5. 生成 JWT token 并返回
    """
    # 1. 手机号唯一性检查
    existing_user = await get_user_by_phone(db, user_data.phone)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="手机号已被注册"
        )

    # 2. 校验邀请码
    invite_code_record = await get_valid_invite_code(db, user_data.invite_code)
    if not invite_code_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="邀请码无效或已过期"
        )

    # 3. 创建用户和状态
    try:
        new_user = await create_user(db, user_data.phone, user_data.password, user_data.invite_code)
        await create_user_status(db, new_user.id)
        await delete_invite_code(db, user_data.invite_code)
        # await db.commit() 这里不提交，保证整个注册都在一个事务。
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册失败，请稍后重试"
        )

    # 4. 生成 token 与 jti
    token, jti = create_access_token_with_jti(data={"sub": new_user.phone})

    # 5. 解析 IP 与城市
    client_ip = get_client_ip(request)
    try:
        location = get_city_from_ip(client_ip)
    except Exception:
        location = None  # 解析失败只记空，不影响登录

    # 6. 更新用户当前会话字段
    new_user.current_token_jti = jti
    new_user.current_login_ip = client_ip
    new_user.current_location = location

    # 7. 插入登录历史
    device_info = request.headers.get("user-agent", "")[:200]
    # 8. 使之前的有效会话失效
    await invalidate_previous_sessions(db, new_user.id)
    await create_login_history(db, new_user.id, client_ip, location, device_info, jti)
    await db.commit()

    token_data = Token(access_token=token)
    logger.info(f"用户 {new_user.phone} 注册成功")
    return success_response(message="注册成功", data=token_data)


@router.post("/login", summary="登录")
async def login(
    request: Request,
    user_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    登录流程：
    - 普通用户：验证手机号+密码，直接返回 token 等信息
    - 管理员手机号：验证一级密码后，发送邮件并返回 require_second_factor: true（若IP与上次相同则跳过邮件）
    """
    phone = user_data.phone
    password = user_data.password

    # 检查是否为管理员手机号
    if phone == ADMIN_PHONE:
        # 检查管理员登录功能是否启用
        if not await is_admin_login_enabled(db):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="管理员登录入口已关闭"
            )

        # 验证一级密码（明文 vs 哈希）
        if not verify_password(password, ADMIN_1ST_PWD_HASH):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="手机号或密码错误"
            )

        # 获取客户端IP
        client_ip = get_client_ip(request)

        # 写入一级验证成功日志
        await create_admin_log(
            db=db,
            admin_phone=phone,
            action_type="ADMIN_LOGIN_STAGE1",
            request_ip=client_ip,
            user_agent=request.headers.get("user-agent"),
            remark="管理员一级验证成功"
        )

        # 检查 24 小时内同一 IP 的一级验证尝试次数
        attempts = await count_admin_stage1_attempts_last_24h(db, client_ip, phone)
        if attempts > 3:  # 第4次及以上被拒绝
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="今日管理员一级验证尝试次数已达上限，请24小时后再试"
            )

        # ---------- 根据最近一次成功一级验证的 IP 决定是否发送邮件 ----------
        # 查询最近两次一级验证成功的记录（按时间倒序），第一条是本次刚写入的，取第二条作为“上一次”
        previous_ip_stmt = (
            select(AdminLog.request_ip)
            .where(AdminLog.admin_phone == phone,
                   AdminLog.action_type == "ADMIN_LOGIN_STAGE1")
            .order_by(desc(AdminLog.created_at))
            .limit(2)
        )
        result = await db.execute(previous_ip_stmt)
        ip_records = result.scalars().all()

        should_send_mail = True
        if len(ip_records) >= 2:
            previous_ip = ip_records[1]  # 第二条为上一次成功登录的IP
            if previous_ip == client_ip:
                should_send_mail = False

        try:
            if should_send_mail:
                login_time = datetime.now()
                send_admin_login_alert(client_ip, login_time)
            else:
                logger.info("与上次管理员登录 IP 相同，跳过发送管理员登录提醒")
        except Exception as e:
            # 邮件发送失败不应影响登录流程，仅记录日志
            logger.error(f"发送管理员登录提醒失败: {e}", exc_info=True)

        # 记录待验证会话
        pending_admin_verifications[phone] = time.time() + PENDING_EXPIRE_SECONDS

        # 返回需要二级验证的标志
        return success_response(
            message="一级验证通过，需要二级密码验证",
            data={"require_second_factor": True, "phone": phone}
        )

    # 普通用户登录流程
    user = await get_user_by_phone(db, phone)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="手机号或密码错误"
        )

    if not user.can_login:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁止登录，请联系管理员"
        )

    if not verify_password(password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="手机号或密码错误"
        )

    token, jti = create_access_token_with_jti(data={"sub": user.phone})
    client_ip = get_client_ip(request)
    # client_ip = "101.132.178.179"  # 测试用 上海
    # client_ip = "117.136.110.125"  # 测试用 江西
    try:
        location = get_city_from_ip(client_ip)
    except Exception:
        location = None  # 解析失败只记空，不影响登录

    user.current_token_jti = jti
    user.current_login_ip = client_ip
    user.current_location = location

    # 旧会话失效
    await invalidate_previous_sessions(db, user.id)
    login_record = await create_login_history(
        db, user.id, client_ip, location,
        request.headers.get("user-agent", "")[:200], jti
    )
    await db.commit()

    token_data = Token(access_token=token)

    # ---------- 异地登录提醒 ----------
    # 查询最近一次已失效的登录记录（不包含本次刚写入的记录）
    await db.flush()   # ✅ 确保 login_record.id 被赋值
    prev_login_stmt = (
        select(LoginHistory)
        .where(LoginHistory.user_id == user.id, LoginHistory.id != login_record.id)
        .order_by(desc(LoginHistory.created_at))
        .limit(1)
    )
    prev_result = await db.execute(prev_login_stmt)
    prev_login = prev_result.scalar_one_or_none()

    login_alert = None
    if prev_login:
        prev_loc = prev_login.location
        cur_loc = location

        # 优先用城市比较，如果都有城市且不同，才提醒；否则降级比较 IP
        if prev_loc and cur_loc:
            if prev_loc != cur_loc:
                login_alert = (
                    f"⚠️ 检测到异地登录：上次登录地点 {prev_loc}，"
                    f"本次为 {cur_loc}。如非本人操作，请及时修改密码。"
                )
        else:
            # 任一城市缺失，回退到 IP 比较
            if prev_login.login_ip != client_ip:
                prev_str = prev_loc or "未知地区"
                cur_str = cur_loc or "未知地区"
                login_alert = (
                    f"⚠️ 检测到异地登录：上次登录地点 {prev_str}，"
                    f"本次为 {cur_str}。如非本人操作，请及时修改密码。"
                )

    # 将 Token 对象转为字典，再添加 login_alert（不破坏原有结构）
    return_dict = token_data.model_dump()
    return_dict["login_alert"] = login_alert

    logger.info(f"用户 {user.phone} 登录成功")
    return success_response(message="登录成功", data=return_dict)


ADMIN_PATH_PREFIX = os.getenv("ADMIN_PATH_PREFIX", "/admin_default")


@router.post("/admin/second-verify", summary="管理员二级验证")
async def admin_second_verify(
    request: Request,
    body: AdminSecondVerifyRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    二级密码验证，通过后生成管理员 token（有效期 1 小时）
    """
    phone = body.phone
    second_password = body.second_password
    # 校验手机号是否为管理员
    if phone != ADMIN_PHONE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="无效的请求"
        )

    # 检查是否在待验证列表中且未过期
    expire_ts = pending_admin_verifications.get(phone)
    if expire_ts is None or time.time() > expire_ts:
        pending_admin_verifications.pop(phone, None)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="二级验证会话已过期，请重新登录"
        )

    # 验证二级密码（明文 vs 哈希）
    if not verify_password(second_password, ADMIN_2ND_PWD_HASH):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="二级密码错误"
        )

    # 清除待验证记录
    pending_admin_verifications.pop(phone, None)

    # 记录二级验证成功日志
    await create_admin_log(
        db=db,
        admin_phone=phone,
        action_type="ADMIN_LOGIN_SUCCESS",
        request_ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        remark="管理员二级验证成功，登录后台"
    )

    # 生成管理员 token，有效期 1 小时（改成 24 小时方便测试）
    access_token = create_access_token(
        data={"sub": phone, "is_admin": True},
        expires_delta=timedelta(hours=1)
    )
    # 在函数末尾，替换原来的 success_response
    redirect_url = f"{ADMIN_PATH_PREFIX}/admin.html"

    logger.info("管理员二级验证成功，生成 token")
    return success_response(
        message="管理员验证通过",
        data=AdminSecondVerifyResponseData(
            access_token=access_token,
            token_type="bearer",
            admin_redirect_url=redirect_url
        )
    )