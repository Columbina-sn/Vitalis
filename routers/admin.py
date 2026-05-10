# routers/admin.py
import os
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Request, Query, Body, HTTPException, Path
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from config.db_conf import get_db
from core.deps import get_current_admin_user
from crud.admin import get_admin_stats, create_admin_log, batch_create_invite_codes, get_admin_logs_cursor_paginated, \
    disable_admin_login, get_users_paginated, get_comments_paginated, get_invite_codes_paginated, \
    get_admin_logs_all_paginated, get_user_by_id_admin, update_user_admin, soft_delete_user_admin, get_comment_by_id, \
    update_comment_admin, soft_delete_comment_admin, get_invite_code_by_id, update_invite_code_admin, \
    delete_invite_code_admin, delete_admin_log_by_id, get_deleted_users_paginated, get_deleted_comments_paginated, \
    restore_user_admin, restore_comment_admin
from models import AdminLog
from schemas.admin import AdminStatsResponse, BatchInviteCodeRequest, BatchInviteCodeResponse, AdminLogItem, \
    AdminLogCursor, AdminLogsResponse, UserInAdminList, AdminUserListResponse, CommentInAdminList, \
    AdminCommentListResponse, InviteCodeItem, AdminInviteCodeListResponse, AdminLogItemFull, AdminLogListResponse, \
    UpdateUserRequest, UpdateCommentRequest, UpdateInviteCodeRequest
from tasks import daily_summary_task, cleanup_soft_deleted_records, backup_database_task
from utills.response import success_response
from utills.ip_utils import get_client_ip
from utills.logging_conf import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/admin", tags=["管理员"])

# -- 头像清理用到的配置（与用户注销接口保持一致） --
AVATAR_UPLOAD_DIR = os.getenv("AVATAR_UPLOAD_DIR", "static_pic/avatar")
DEFAULT_AVATAR_URL = os.getenv("DEFAULT_AVATAR_URL", "/static_pic/default_avatar.jpg")


@router.get("/stats", summary="获取管理后台统计数据")
async def admin_stats(
        request: Request,
        current_admin: dict = Depends(get_current_admin_user),
        db: AsyncSession = Depends(get_db)
):
    """
    返回系统统计数据：用户总数、今日对话数、评论总数、有效邀请码数。
    需要管理员权限，并记录操作日志。
    """
    # 1. 查询统计数据
    stats = await get_admin_stats(db)

    # 2. 不记录操作日志了 乱死了
    # await create_admin_log(
    #     db=db,
    #     admin_phone=current_admin["phone"],
    #     action_type="VIEW_STATS",
    #     request_ip=get_client_ip(request),
    #     user_agent=request.headers.get("user-agent"),
    #     remark="获取系统统计数据"
    # )

    # 3. 返回统一成功响应
    return success_response(message="返回统计数据成功", data=AdminStatsResponse(**stats).model_dump())


@router.post("/invite-codes/batch", summary="批量生成邀请码")
async def batch_generate_invite_codes(
        request: Request,
        req: BatchInviteCodeRequest,
        current_admin: dict = Depends(get_current_admin_user),
        db: AsyncSession = Depends(get_db)
):
    """
    管理员批量生成邀请码，数量 1-100，有效期 1-7 天。
    返回生成的邀请码列表及统一的过期时间。
    """
    # 1. 调用 CRUD 生成邀请码
    codes, expiry_time = await batch_create_invite_codes(
        db=db,
        count=req.count,
        expiry_days=req.expiry_days
    )

    # 2. 记录操作日志
    await create_admin_log(
        db=db,
        admin_phone=current_admin["phone"],
        action_type="BATCH_INVITE",
        request_ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        remark=f"批量生成 {req.count} 个邀请码，有效期 {req.expiry_days} 天"
    )

    logger.info(f"管理员 {current_admin['phone']} 批量生成 {req.count} 个邀请码")

    # 3. 返回统一成功响应
    return success_response(
        message=f"成功生成 {req.count} 个邀请码",
        data=BatchInviteCodeResponse(
            codes=codes,
            expiry_time=expiry_time.isoformat()
        ).model_dump()
    )


@router.get("/logs", summary="查询管理员操作日志")
async def get_admin_logs(
        request: Request,
        start_date: Optional[date] = Query(None, description="开始日期（YYYY-MM-DD）"),
        end_date: Optional[date] = Query(None, description="结束日期（YYYY-MM-DD）"),
        cursor_created_at: Optional[datetime] = Query(None, description="上一页最后一条的创建时间（ISO格式）"),
        cursor_id: Optional[int] = Query(None, description="上一页最后一条的ID"),
        page_size: int = Query(20, ge=1, le=100, description="每页条数"),
        current_admin: dict = Depends(get_current_admin_user),
        db: AsyncSession = Depends(get_db)
):
    # 将 date 类型转换为 datetime
    start_dt = datetime.combine(start_date, datetime.min.time()) if start_date else None
    end_dt = datetime.combine(end_date, datetime.max.time()) if end_date else None

    logs, next_cursor = await get_admin_logs_cursor_paginated(
        db=db,
        start_date=start_dt,
        end_date=end_dt,
        cursor_created_at=cursor_created_at,
        cursor_id=cursor_id,
        page_size=page_size
    )

    if cursor_created_at is None and cursor_id is None:
        await create_admin_log(
            db=db,
            admin_phone=current_admin["phone"],
            action_type="VIEW_LOGS",
            request_ip=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            remark=f"查询操作日志，日期范围: {start_date} ~ {end_date}"
        )

    log_items = [
        AdminLogItem(
            id=log.id,
            admin_phone=log.admin_phone,
            action_type=log.action_type,
            remark=log.remark,
            created_at=log.created_at
        )
        for log in logs
    ]

    next_cursor_obj = None
    if next_cursor:
        next_cursor_obj = AdminLogCursor(
            created_at=next_cursor[0],
            id=next_cursor[1]
        )

    return success_response(
        message="日志查询成功",
        data=AdminLogsResponse(
            list=log_items,
            next_cursor=next_cursor_obj
        ).model_dump()
    )


@router.post("/system-config/disable", summary="关闭管理员登录入口")
async def close_admin_login(
        request: Request,
        current_admin: dict = Depends(get_current_admin_user),
        db: AsyncSession = Depends(get_db)
):
    """
    管理员一键熔断：将 admin_login_enabled 设为 false。
    关闭后，管理后台所有接口（包括本接口）仍可正常调用一次（用于确认关闭），
    但之后新建会话将无法通过管理员身份校验。
    """
    # 执行关闭操作
    success = await disable_admin_login(db)
    if not success:
        return success_response(message="admin_login_enabled 配置项不存在，请检查数据库", data={})

    # 记录操作日志
    await create_admin_log(
        db=db,
        admin_phone=current_admin["phone"],
        action_type="TOGGLE_CONFIG",
        request_ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        target_table="system_config",
        target_id=None,
        before_snapshot={"admin_login_enabled": "true"},  # 简化快照，实际可查询原值
        after_snapshot={"admin_login_enabled": "false"},
        remark="管理员关闭登录入口 (admin_login_enabled → false)"
    )

    logger.warning(f"管理员 {current_admin['phone']} 关闭了管理员登录入口")
    return success_response(message="管理员登录入口已关闭", data={})


@router.get("/users", summary="分页获取所有用户列表")
async def get_admin_users(
        page: int = Query(1, ge=1, description="页码"),
        page_size: int = Query(20, ge=1, le=100, description="每页条数"),
        db: AsyncSession = Depends(get_db),
        _admin: dict = Depends(get_current_admin_user)  # 用 _admin 表示仅用于鉴权，不读取内容
):
    users, total = await get_users_paginated(db, page, page_size)
    user_items = [UserInAdminList(**user) for user in users]
    return success_response(
        message="用户列表查询成功",
        data=AdminUserListResponse(total=total, list=user_items).model_dump()
    )


@router.get("/comments", summary="分页获取所有评论列表")
async def get_admin_comments(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        _admin: dict = Depends(get_current_admin_user)
):
    comments, total = await get_comments_paginated(db, page, page_size)
    comment_items = [
        CommentInAdminList(
            id=c.id, content=c.content, ip_address=c.ip_address, replied=c.replied, created_at=c.created_at
        )
        for c in comments
    ]
    return success_response(
        message="评论列表查询成功",
        data=AdminCommentListResponse(total=total, list=comment_items).model_dump()
    )


@router.get("/invite-codes", summary="分页获取所有邀请码")
async def get_admin_invite_codes(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        _admin: dict = Depends(get_current_admin_user)
):
    codes, total = await get_invite_codes_paginated(db, page, page_size)
    code_items = [
        InviteCodeItem(id=c.id, code=c.code, expiry_time=c.expiry_time)
        for c in codes
    ]
    return success_response(
        message="邀请码列表查询成功",
        data=AdminInviteCodeListResponse(total=total, list=code_items).model_dump()
    )


@router.get("/logs-all", summary="分页获取所有操作日志（全量）")
async def get_admin_logs_all(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        _admin: dict = Depends(get_current_admin_user)
):
    logs, total = await get_admin_logs_all_paginated(db, page, page_size)
    log_items = [
        AdminLogItemFull(
            id=log.id,
            admin_phone=log.admin_phone,
            action_type=log.action_type,
            remark=log.remark,
            created_at=log.created_at
        )
        for log in logs
    ]
    return success_response(
        message="操作日志查询成功",
        data=AdminLogListResponse(total=total, list=log_items).model_dump()
    )


# ---------- 用户编辑与删除 ----------
@router.put("/users/{user_id}", summary="编辑用户")
async def update_user(
        user_id: int = Path(..., ge=1),
        req: UpdateUserRequest = Body(...),
        request: Request = None,
        current_admin: dict = Depends(get_current_admin_user),
        db: AsyncSession = Depends(get_db)
):
    user = await get_user_by_id_admin(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    before_snapshot = {
        "phone": user.phone,
        "nickname": user.nickname,
        "can_login": user.can_login
    }
    await update_user_admin(db, user_id, req.phone, req.nickname, req.can_login)
    after_snapshot = {
        "phone": req.phone,
        "nickname": req.nickname,
        "can_login": req.can_login
    }
    await create_admin_log(
        db, admin_phone=current_admin["phone"],
        action_type="UPDATE_USER",
        target_table="users", target_id=user_id,
        before_snapshot=before_snapshot, after_snapshot=after_snapshot,
        request_ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        remark=f"修改用户 {user.phone} 的信息"
    )
    logger.info(f"管理员 {current_admin['phone']} 编辑用户 {user_id}")
    return success_response(message="用户信息已更新")


# routers/admin.py 中的相关接口修改

@router.delete("/users/{user_id}", summary="删除用户")
async def delete_user(
        user_id: int = Path(...),
        request: Request = None,
        current_admin: dict = Depends(get_current_admin_user),
        db: AsyncSession = Depends(get_db)
):
    user = await get_user_by_id_admin(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    before_snapshot = {"phone": user.phone, "nickname": user.nickname, "is_deleted": user.is_deleted}

    # 软删除（不清理头像，等物理删除时再清）
    await soft_delete_user_admin(db, user_id)

    await create_admin_log(
        db, admin_phone=current_admin["phone"],
        action_type="DELETE_USER",   # 也可以改用 "SOFT_DELETE_USER"，此处保持兼容
        target_table="users", target_id=user_id,
        before_snapshot=before_snapshot,
        after_snapshot={"is_deleted": True, "deleted_at": datetime.now().isoformat()},
        request_ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        remark=f"软删除用户 {user.phone}，数据保留30天后将彻底清除"
    )
    logger.info(f"管理员 {current_admin['phone']} 软删除用户 {user_id}")
    return success_response(message="用户已标记删除")


# ---------- 评论编辑与删除 ----------
@router.put("/comments/{comment_id}", summary="编辑评论")
async def update_comment(
        comment_id: int = Path(...),
        req: UpdateCommentRequest = Body(...),
        request: Request = None,
        current_admin: dict = Depends(get_current_admin_user),
        db: AsyncSession = Depends(get_db)
):
    comment = await get_comment_by_id(db, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")
    before_snapshot = {"content": comment.content, "replied": comment.replied}
    await update_comment_admin(db, comment_id, req.content, req.replied)
    await create_admin_log(
        db, admin_phone=current_admin["phone"],
        action_type="UPDATE_COMMENT",
        target_table="comment", target_id=comment_id,
        before_snapshot=before_snapshot,
        after_snapshot={"content": req.content, "replied": req.replied},
        request_ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        remark=f"编辑评论 ID：{comment_id}"
    )
    logger.info(f"管理员 {current_admin['phone']} 编辑评论 {comment_id}")
    return success_response(message="评论已更新")


@router.delete("/comments/{comment_id}", summary="删除评论")
async def delete_comment(
        comment_id: int = Path(...),
        request: Request = None,
        current_admin: dict = Depends(get_current_admin_user),
        db: AsyncSession = Depends(get_db)
):
    comment = await get_comment_by_id(db, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="评论不存在")
    before_snapshot = {"content": comment.content, "is_deleted": comment.is_deleted}

    await soft_delete_comment_admin(db, comment_id)

    await create_admin_log(
        db, admin_phone=current_admin["phone"],
        action_type="DELETE_COMMENT",
        target_table="comment", target_id=comment_id,
        before_snapshot=before_snapshot,
        after_snapshot={"is_deleted": True, "deleted_at": datetime.now().isoformat()},
        request_ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        remark=f"软删除评论 ID：{comment_id}"
    )
    logger.info(f"管理员 {current_admin['phone']} 软删除评论 {comment_id}")
    return success_response(message="评论已标记删除")


# ---------- 邀请码编辑与删除 ----------
@router.put("/invite-codes/{invite_id}", summary="编辑邀请码")
async def update_invite_code(
        invite_id: int = Path(...),
        req: UpdateInviteCodeRequest = Body(...),
        request: Request = None,
        current_admin: dict = Depends(get_current_admin_user),
        db: AsyncSession = Depends(get_db)
):
    invite = await get_invite_code_by_id(db, invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    before_snapshot = {"code": invite.code, "expiry_time": invite.expiry_time.isoformat()}
    await update_invite_code_admin(db, invite_id, req.code, req.expiry_time)
    await create_admin_log(
        db, admin_phone=current_admin["phone"],
        action_type="UPDATE_INVITE_CODE",
        target_table="invite_code", target_id=invite_id,
        before_snapshot=before_snapshot,
        after_snapshot={"code": req.code, "expiry_time": req.expiry_time.isoformat()},
        request_ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        remark=f"编辑邀请码 ID：{invite_id}"
    )
    logger.info(f"管理员 {current_admin['phone']} 编辑邀请码 {invite_id}")
    return success_response(message="邀请码已更新")


@router.delete("/invite-codes/{invite_id}", summary="删除邀请码")
async def delete_invite_code(
        invite_id: int = Path(...),
        request: Request = None,
        current_admin: dict = Depends(get_current_admin_user),
        db: AsyncSession = Depends(get_db)
):
    invite = await get_invite_code_by_id(db, invite_id)
    if not invite:
        raise HTTPException(status_code=404, detail="邀请码不存在")
    before_snapshot = {"code": invite.code}
    await delete_invite_code_admin(db, invite_id)
    await create_admin_log(
        db, admin_phone=current_admin["phone"],
        action_type="DELETE_INVITE_CODE",
        target_table="invite_code", target_id=invite_id,
        before_snapshot=before_snapshot, after_snapshot=None,
        request_ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        remark=f"删除邀请码 ID：{invite_id}"
    )
    logger.info(f"管理员 {current_admin['phone']} 删除邀请码 {invite_id}")
    return success_response(message="邀请码已删除")


# ---------- 日志删除 ----------
@router.delete("/logs/{log_id}", summary="删除单条操作日志")
async def delete_admin_log(
        log_id: int = Path(...),
        request: Request = None,
        current_admin: dict = Depends(get_current_admin_user),
        db: AsyncSession = Depends(get_db)
):
    log = await db.get(AdminLog, log_id)
    if not log:
        raise HTTPException(status_code=404, detail="日志记录不存在")
    await delete_admin_log_by_id(db, log_id)
    logger.info(f"管理员 {current_admin['phone']} 删除日志 {log_id}")
    return success_response(message="日志已删除")


@router.get("/daily-summary/status", summary="查询今日是否已触发每日摘要（自动或手动）")
async def daily_summary_status(
        current_admin: dict = Depends(get_current_admin_user),
        db: AsyncSession = Depends(get_db)
):
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())
    stmt = select(func.count()).select_from(AdminLog).where(
        AdminLog.action_type.in_(['DAILY_SUMMARY', 'MANUAL_DAILY_SUMMARY']),
        AdminLog.created_at >= today_start,
        AdminLog.created_at <= today_end
    )
    result = await db.execute(stmt)
    count = result.scalar() or 0
    return success_response(message="查询成功", data={"alreadyTriggered": count > 0})


@router.post("/daily-summary/trigger", summary="手动触发每日摘要生成")
async def trigger_daily_summary(
        request: Request,
        current_admin: dict = Depends(get_current_admin_user),
        db: AsyncSession = Depends(get_db)
):
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())
    stmt = select(func.count()).select_from(AdminLog).where(
        AdminLog.action_type.in_(['DAILY_SUMMARY', 'MANUAL_DAILY_SUMMARY']),
        AdminLog.created_at >= today_start,
        AdminLog.created_at <= today_end
    )
    result = await db.execute(stmt)
    if (result.scalar() or 0) > 0:
        raise HTTPException(status_code=409, detail="今天已经触发过每日摘要生成（自动或手动），不可重复执行")

    await daily_summary_task(
        admin_phone=current_admin["phone"],
        action_type="MANUAL_DAILY_SUMMARY",
        request_ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        remark_prefix="管理员主动触发"
    )
    logger.info(f"管理员 {current_admin['phone']} 手动触发每日摘要生成")
    return success_response(message="每日摘要生成任务已启动")


# ---------- 已删除用户/评论列表 ----------
@router.get("/users/deleted", summary="分页获取已删除用户")
async def get_deleted_users(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        _admin: dict = Depends(get_current_admin_user)
):
    users, total = await get_deleted_users_paginated(db, page, page_size)
    user_items = [UserInAdminList(**user) for user in users]
    return success_response(
        message="已删除用户列表查询成功",
        data=AdminUserListResponse(total=total, list=user_items).model_dump()
    )


@router.get("/comments/deleted", summary="分页获取已删除评论")
async def get_deleted_comments(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        db: AsyncSession = Depends(get_db),
        _admin: dict = Depends(get_current_admin_user)
):
    comments, total = await get_deleted_comments_paginated(db, page, page_size)
    comment_items = [
        CommentInAdminList(
            id=c.id, content=c.content, ip_address=c.ip_address, replied=c.replied, created_at=c.created_at
        )
        for c in comments
    ]
    return success_response(
        message="已删除评论列表查询成功",
        data=AdminCommentListResponse(total=total, list=comment_items).model_dump()
    )


# ---------- 还原操作 ----------
@router.put("/users/{user_id}/restore", summary="还原已删除用户")
async def restore_user(
        user_id: int = Path(...),
        request: Request = None,
        current_admin: dict = Depends(get_current_admin_user),
        db: AsyncSession = Depends(get_db)
):
    user = await get_user_by_id_admin(db, user_id)
    if not user or not user.is_deleted:
        raise HTTPException(status_code=404, detail="用户不存在或未被删除")
    await restore_user_admin(db, user_id)
    await create_admin_log(
        db, admin_phone=current_admin["phone"],
        action_type="RESTORE_USER",
        target_table="users", target_id=user_id,
        request_ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        remark=f"还原用户 {user.phone} 的数据"
    )
    logger.info(f"管理员 {current_admin['phone']} 还原用户 {user_id}")
    return success_response(message="用户已还原")


@router.put("/comments/{comment_id}/restore", summary="还原已删除评论")
async def restore_comment(
        comment_id: int = Path(...),
        request: Request = None,
        current_admin: dict = Depends(get_current_admin_user),
        db: AsyncSession = Depends(get_db)
):
    comment = await get_comment_by_id(db, comment_id)
    if not comment or not comment.is_deleted:
        raise HTTPException(status_code=404, detail="评论不存在或未被删除")
    await restore_comment_admin(db, comment_id)
    await create_admin_log(
        db, admin_phone=current_admin["phone"],
        action_type="RESTORE_COMMENT",
        target_table="comment", target_id=comment_id,
        request_ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        remark=f"还原评论 ID：{comment_id}"
    )
    logger.info(f"管理员 {current_admin['phone']} 还原评论 {comment_id}")
    return success_response(message="评论已还原")


# ---------- 手动触发数据清理 ----------
@router.get("/cleanup/status", summary="查询今日是否已触发手动清理")
async def cleanup_status(
        current_admin: dict = Depends(get_current_admin_user),
        db: AsyncSession = Depends(get_db)
):
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())
    stmt = select(func.count()).select_from(AdminLog).where(
        AdminLog.action_type == 'MANUAL_CLEANUP',
        AdminLog.created_at >= today_start,
        AdminLog.created_at <= today_end
    )
    result = await db.execute(stmt)
    count = result.scalar() or 0
    return success_response(message="查询成功", data={"alreadyTriggered": count > 0})


@router.post("/cleanup/trigger", summary="手动触发数据清理")
async def trigger_cleanup(
        request: Request,
        current_admin: dict = Depends(get_current_admin_user),
        db: AsyncSession = Depends(get_db)
):
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())
    stmt = select(func.count()).select_from(AdminLog).where(
        AdminLog.action_type == 'MANUAL_CLEANUP',
        AdminLog.created_at >= today_start,
        AdminLog.created_at <= today_end
    )
    result = await db.execute(stmt)
    if (result.scalar() or 0) > 0:
        raise HTTPException(status_code=409, detail="今天已经触发过手动清理，不可重复执行")

    # 调用任务函数，传入管理员信息用于日志记录
    await cleanup_soft_deleted_records(
        admin_phone=current_admin["phone"],
        action_type="MANUAL_CLEANUP",
        request_ip=get_client_ip(request),
        remark_prefix="管理员手动触发"
    )
    logger.info(f"管理员 {current_admin['phone']} 手动触发数据清理")
    return success_response(message="数据清理任务已启动")


# ---------- 手动触发数据库备份 ----------
@router.get("/backup/status", summary="查询今日是否已有备份（自动或手动）")
async def backup_status(
    current_admin: dict = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())
    stmt = select(func.count()).select_from(AdminLog).where(
        AdminLog.action_type.in_(['AUTO_BACKUP', 'MANUAL_BACKUP']),
        AdminLog.created_at >= today_start,
        AdminLog.created_at <= today_end
    )
    result = await db.execute(stmt)
    count = result.scalar() or 0
    return success_response(message="查询成功", data={"alreadyTriggered": count > 0})


@router.post("/backup/trigger", summary="手动触发数据库备份")
async def trigger_backup(
    request: Request,
    current_admin: dict = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db)
):
    # 检查今日是否已执行过备份（无论自动还是手动）
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_end = datetime.combine(date.today(), datetime.max.time())
    stmt = select(func.count()).select_from(AdminLog).where(
        AdminLog.action_type.in_(['AUTO_BACKUP', 'MANUAL_BACKUP']),
        AdminLog.created_at >= today_start,
        AdminLog.created_at <= today_end
    )
    result = await db.execute(stmt)
    count = result.scalar() or 0
    if count > 0:
        raise HTTPException(
            status_code=409,
            detail="今天已经执行过数据库备份（自动或手动），不可重复执行"
        )

    # 调用备份任务（等待完成，管理员会收到响应）
    await backup_database_task(
        admin_phone=current_admin["phone"],
        action_type="MANUAL_BACKUP",
        request_ip=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        remark_prefix="管理员手动触发"
    )
    logger.info(f"管理员 {current_admin['phone']} 手动触发数据库备份")
    return success_response(message="数据库备份任务已启动并完成")