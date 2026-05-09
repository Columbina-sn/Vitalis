# routers/user.py
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_db
from core.deps import get_current_user
from crud.user import update_user_nickname, update_user_avatar, soft_delete_user_account, get_user_status_by_user_id, \
    update_user_password, get_status_history_by_dimension, get_user_export_data_html, \
    get_user_schedules, update_user_theme_mode
from models import User
from schemas.user import (
    UserBaseInfoResponse,
    UserInfoResponse,
    UpdateNicknameRequest,
    UpdateAvatarResponse,
    DeleteAccountRequest,
    UserStatusResponse,
    ChangePasswordRequest,
    StatusDimension,
    StatusHistoryResponse,
    StatusHistoryItem, UserScheduleResponse, UpdateThemeModeRequest
)
from utills.html_export import generate_export_html
from utills.psychological_harmony_index import calculate_phi
from utills.response import success_response
from utills.security import verify_password, get_hash_password

router = APIRouter(prefix="/user", tags=["用户"])

# ========== 从环境变量读取配置 ==========
AVATAR_UPLOAD_DIR = os.getenv("AVATAR_UPLOAD_DIR", "uploads/avatars")
DEFAULT_AVATAR_URL = os.getenv("DEFAULT_AVATAR_URL", "/static/placeholder_avatar.png")
# MAX_AVATAR_SIZE = int(os.getenv("MAX_AVATAR_SIZE", 5 * 1024 * 1024))  # 默认 5MB

os.makedirs(AVATAR_UPLOAD_DIR, exist_ok=True)


@router.get("/base-info", summary="获取基本信息（是否新用户，头像URL）")
async def get_base_info(
    current_user: User = Depends(get_current_user),
):
    """获取用户基本信息（是否看过新手引导、头像URL、主题模式）"""
    data = UserBaseInfoResponse(
        has_seen_intro=current_user.has_seen_intro,
        avatar=current_user.avatar or DEFAULT_AVATAR_URL,
        theme_mode=current_user.theme_mode if current_user.theme_mode is not None else 2
    )
    return success_response(message="获取用户基本信息成功", data=data)


@router.get("/status", summary="获取五维状态")
async def get_user_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取当前用户的五维状态值"""
    user_status = await get_user_status_by_user_id(db, current_user.id)
    if not user_status:
        # 理论上注册时已创建，若缺失则返回默认值（全50）
        return success_response(
            message="获取用户状态成功（使用默认值）",
            data=UserStatusResponse(
                physical_vitality=50,
                emotional_tone=50,
                relationship_connection=50,
                self_worth=50,
                meaning_direction=50,
                psychological_harmony_index=calculate_phi(50, 50, 50, 50, 50)
            )
        )
    return success_response(
        message="获取用户状态成功",
        data=UserStatusResponse.model_validate(user_status)
    )


@router.post("/mark-intro", summary="标记为已过引导")
async def mark_intro_seen(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """用户完成新手引导后调用，将 has_seen_intro 设置为 True"""
    current_user.has_seen_intro = True
    await db.commit()
    return success_response(message="标记新手引导完成成功", data={"has_seen_intro": True})


@router.get("/information", summary="获取用户所有信息（手机号、昵称、头像、邀请码、位置）")
async def get_user_info(
    current_user: User = Depends(get_current_user),
):
    """获取用户所有信息（手机号、昵称、头像、邀请码、位置）"""
    data = UserInfoResponse(
        phone=current_user.phone,
        nickname=current_user.nickname,
        avatar=current_user.avatar or DEFAULT_AVATAR_URL,
        invite_code=current_user.invite_code,
        location=current_user.current_location or "未知",
        login_ip=current_user.current_login_ip
    )
    return success_response(message="获取用户信息成功", data=data)


@router.post("/nickname", summary="修改用户昵称")
async def change_nickname(
    req: UpdateNicknameRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修改用户昵称"""
    updated_user = await update_user_nickname(db, current_user.id, req.nickname)
    if not updated_user:
        raise HTTPException(status_code=500, detail="更新失败")
    return success_response(message="修改昵称成功", data={"nickname": updated_user.nickname})


def delete_old_avatar(old_avatar_url: str):
    """安全删除旧头像文件（防止路径遍历）"""
    if not old_avatar_url or old_avatar_url == DEFAULT_AVATAR_URL:
        return
    # 移除开头的斜杠，转换为相对路径
    if old_avatar_url.startswith("/"):
        old_avatar_url = old_avatar_url[1:]
    # 安全提取文件名，防止路径遍历
    filename = os.path.basename(old_avatar_url)
    file_path = os.path.join(AVATAR_UPLOAD_DIR, filename)
    # 确保文件在允许的目录内
    if not os.path.abspath(file_path).startswith(os.path.abspath(AVATAR_UPLOAD_DIR)):
        return
    if os.path.exists(file_path) and os.path.isfile(file_path):
        try:
            os.remove(file_path)
        except Exception as e:
            print(f"删除旧头像失败: {e}")


@router.post("/avatar", summary="修改用户头像")
async def change_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    修改用户头像（支持图片上传）
    1. 验证文件类型（仅图片）和大小
    2. 生成唯一文件名
    3. 保存到配置的头像目录
    4. 删除旧头像（如果不是默认头像）
    5. 返回可访问的 URL
    """
    # 1. 类型检查
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="仅支持 JPEG、PNG、GIF、WEBP 格式的图片"
        )

    # 2. 先读取文件内容
    contents = await file.read()

    # 手动检查文件大小（值从 .env 里的 MAX_AVATAR_SIZE 拿，默认 5MB）
    max_size = int(os.getenv("MAX_AVATAR_SIZE", 5 * 1024 * 1024))
    if len(contents) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件大小不能超过 {max_size // (1024 * 1024)}MB"
        )

    # 3. 生成文件名
    ext = os.path.splitext(file.filename)[1].lower()
    if not ext:
        ext = ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(AVATAR_UPLOAD_DIR, filename)   # AVATAR_UPLOAD_DIR 你原来就有的

    # 4. 保存文件
    try:
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    new_avatar_url = f"/{file_path}"
    old_avatar_url = current_user.avatar

    # 5. 更新数据库
    updated_user = await update_user_avatar(db, current_user.id, new_avatar_url)
    if not updated_user:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail="更新头像失败")

    # 6. 删除旧头像文件
    delete_old_avatar(old_avatar_url)

    return success_response(
        message="修改头像成功",
        data=UpdateAvatarResponse(avatar_url=new_avatar_url)
    )


@router.post("/theme-mode", summary="修改主题模式")
async def change_theme_mode(
    req: UpdateThemeModeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修改用户主题模式（0-浅色，1-深色，2-跟随系统）"""
    updated_user = await update_user_theme_mode(db, current_user.id, req.theme_mode)
    if not updated_user:
        raise HTTPException(status_code=500, detail="主题修改失败")
    await db.commit()
    return success_response(message="主题模式已更新", data={"theme_mode": req.theme_mode})


# routers/user.py 新增接口
@router.post("/logout", summary="安全退出")
async def logout(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """退出登录，清除当前会话"""
    from sqlalchemy import update as sql_update
    from models import LoginHistory

    # 将当前 token 对应的登录历史标记为无效
    # 从依赖注入的 user 对象无法直接拿到 jti，需从 request 或 token 中获取
    # 但此处依赖 get_current_user 已经校验，故可直接利用 user 的 current_token_jti
    # 注意：已经置空，应先保存 jti 再清除
    jti = current_user.current_token_jti  # 保存原有 jti
    current_user.current_token_jti = None
    current_user.current_login_ip = None
    current_user.current_location = None

    if jti:
        await db.execute(
            sql_update(LoginHistory)
            .where(LoginHistory.token_jti == jti, LoginHistory.is_valid == True)
            .values(is_valid=False)
        )
    await db.commit()
    return success_response(message="已安全退出")


@router.post("/delete-account", summary="注销当前用户账户")
async def delete_account(
        req: DeleteAccountRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """
    注销当前用户账户
    1. 验证用户密码
    2. 删除用户上传的头像文件（如果不是默认头像）
    3. 删除数据库中的用户记录（级联删除关联表数据）
    """
    # 验证密码
    if not verify_password(req.password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="密码错误，无法注销账户"
        )

    # 删除用户头像文件（如果不是默认头像）
    if current_user.avatar and current_user.avatar != DEFAULT_AVATAR_URL:
        # 去除开头的斜杠，转换为相对路径
        avatar_path = current_user.avatar.lstrip('/')
        # 安全提取文件名
        filename = os.path.basename(avatar_path)
        file_path = os.path.join(AVATAR_UPLOAD_DIR, filename)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                # 文件删除失败不影响账户注销流程，仅记录日志
                print(f"删除头像文件失败: {e}")

    # 执行软删除
    await soft_delete_user_account(db, current_user)

    return success_response(message="账户已成功注销", data=None)


# @router.get("/recent-events", response_model=RecentEventsResponse, summary="获取当前用户最近三条重大事件")
# async def get_recent_events(
#     current_user: User = Depends(get_current_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """
#     获取当前用户最近三条重大事件（仅返回事件概述）
#     """
#     events = await get_recent_events_by_user_id(db, current_user.id, limit=3)
#     data = RecentEventsResponse(events=events)
#     return success_response(message="获取最近事件成功", data=data)


@router.post("/change-password", summary="修改用户密码")
async def change_password(
    req: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    修改用户密码
    1. 验证旧密码是否正确
    2. 对新密码进行哈希加密
    3. 更新数据库中的密码字段
    """
    # 验证旧密码
    if not verify_password(req.old_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码错误"
        )

    # 再次确保新旧密码不同（已在 Pydantic 校验，但防御性保留）
    if req.old_password == req.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="新密码不能与旧密码相同"
        )

    # 对新密码进行哈希
    hashed_new_pwd = get_hash_password(req.new_password)

    # 更新数据库
    updated_user = await update_user_password(db, current_user.id, hashed_new_pwd)
    if not updated_user:
        raise HTTPException(status_code=500, detail="密码修改失败")

    await db.commit()
    return success_response(message="密码修改成功")


@router.get("/status-history/{dimension}", response_model=StatusHistoryResponse, summary="获取当前用户在指定维度上的近10次历史状态记录")
async def get_status_history(
    dimension: StatusDimension,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    获取当前用户在指定维度上的近16次历史状态记录
    - dimension: 必须为 physical_vitality, emotional_tone, relationship_connection, self_worth, meaning_direction, psychological_harmony_index 之一
    """
    history_data = await get_status_history_by_dimension(
        db, current_user.id, dimension.value, limit=16
    )
    items = [StatusHistoryItem(recorded_at=item["recorded_at"], value=item["value"]) for item in history_data]
    return StatusHistoryResponse(dimension=dimension, history=items)


@router.get("/export", summary="导出用户数据")
async def export_user_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    data = await get_user_export_data_html(db, current_user.id)
    if not data:
        raise HTTPException(404, "用户数据不存在")

    html_content = generate_export_html(data)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"vitalis_report_{current_user.id}_{timestamp}.html"

    return HTMLResponse(
        content=html_content,
        status_code=200,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/schedules", response_model=UserScheduleResponse, summary="获取当前用户所有日程")
async def get_schedules(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户所有日程，按是否完成分类并各自排序"""
    data = await get_user_schedules(db, current_user.id)
    return success_response(message="获取日程成功", data=data)