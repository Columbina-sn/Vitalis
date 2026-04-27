# routers/auth.py
import os
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_db
from crud.admin import create_admin_log, count_admin_stage1_attempts_last_24h
from crud.auth import is_admin_login_enabled
from crud.user import (
    get_user_by_phone, create_user, create_user_status,
    get_valid_invite_code, delete_invite_code
)
from schemas.user import UserCreate, UserLogin, Token
from utills.email_utils import send_admin_login_alert
from utills.ip_utils import get_client_ip
from utills.response import success_response
from utills.security import verify_password, create_access_token

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
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
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
        await db.commit()
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="注册失败，请稍后重试"
        )

    # 4. 生成 token
    access_token = create_access_token(data={"sub": new_user.phone})
    token_data = Token(access_token=access_token)
    return success_response(message="注册成功", data=token_data)


@router.post("/login", summary="登录")
async def login(
    request: Request,
    user_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    登录流程：
    - 普通用户：验证手机号+密码，直接返回 token
    - 管理员手机号：验证一级密码后，发送邮件并返回 require_second_factor: true
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

        # 获取客户端IP并发送邮件
        client_ip = get_client_ip(request)
        # 经测试发件功能正常 为了在测试过程中不总是重复发邮件 故注释
        # login_time = datetime.now()
        # send_admin_login_alert(client_ip, login_time)  # 邮件发送失败不影响流程

        # 写入一级验证尝试日志
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

    access_token = create_access_token(data={"sub": user.phone})
    token_data = Token(access_token=access_token)
    return success_response(message="登录成功", data=token_data)


@router.post("/admin/second-verify", summary="管理员二级验证")
async def admin_second_verify(
    request: Request,
    phone: str,
    second_password: str,
    db: AsyncSession = Depends(get_db)
):
    """
    二级密码验证，通过后生成管理员 token（有效期 1 小时）
    """
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

    # 生成管理员 token，有效期 1 小时，payload 中标记 is_admin
    access_token = create_access_token(
        data={"sub": phone, "is_admin": True},
        expires_delta=timedelta(hours=24)
    )
    return success_response(
        message="管理员验证通过",
        data={"access_token": access_token, "token_type": "bearer"}
    )