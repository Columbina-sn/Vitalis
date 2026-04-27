# crud/admin.py
import string
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple

from sqlalchemy import select, func, tuple_, and_
from sqlalchemy import update as sql_update,  delete as sql_delete
from sqlalchemy.ext.asyncio import AsyncSession

from models import AdminLog, ConversationHistory, InviteCode, Comment, User, SystemConfig


async def create_admin_log(
        db: AsyncSession,
        admin_phone: str,
        action_type: str,
        request_ip: str,
        user_agent: Optional[str] = None,
        target_table: Optional[str] = None,
        target_id: Optional[int] = None,
        before_snapshot: Optional[Dict[str, Any]] = None,
        after_snapshot: Optional[Dict[str, Any]] = None,
        remark: Optional[str] = None
) -> AdminLog:
    """
    创建管理员操作日志记录
    """
    log_entry = AdminLog(
        admin_phone=admin_phone,
        action_type=action_type,
        target_table=target_table,
        target_id=target_id,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        request_ip=request_ip,
        user_agent=user_agent,
        remark=remark,
        created_at=datetime.now()
    )
    db.add(log_entry)
    await db.flush()
    return log_entry


async def count_admin_stage1_attempts_last_24h(
        db: AsyncSession,
        ip_address: str,
        admin_phone: str
) -> int:
    since = datetime.now() - timedelta(hours=24)

    # 1. 查找最近一次二级成功的时间
    last_success_stmt = (
        select(AdminLog.created_at)
        .where(
            AdminLog.request_ip == ip_address,
            AdminLog.admin_phone == admin_phone,
            AdminLog.action_type == "ADMIN_LOGIN_SUCCESS",
            AdminLog.created_at >= since
        )
        .order_by(AdminLog.created_at.desc())
        .limit(1)
    )
    last_success_result = await db.execute(last_success_stmt)
    last_success_time = last_success_result.scalar()

    # 2. 统计在该时间之后的一级尝试次数（若没有成功记录，则统计所有一级尝试）
    if last_success_time:
        effective_since = last_success_time
    else:
        effective_since = since

    stmt = (
        select(func.count())
        .select_from(AdminLog)
        .where(
            AdminLog.request_ip == ip_address,
            AdminLog.action_type == "ADMIN_LOGIN_STAGE1",
            AdminLog.created_at >= effective_since
        )
    )
    result = await db.execute(stmt)
    return result.scalar() or 0


async def get_admin_stats(db: AsyncSession) -> Dict[str, int]:
    """
    获取管理后台统计数据：
    - 用户总数
    - 今日总对话数
    - 评论总数
    - 当前有效的邀请码数
    """
    # 用户总数
    total_users_result = await db.execute(select(func.count()).select_from(User))
    total_users = total_users_result.scalar() or 0

    # 今日对话数 (created_at >= 今日 00:00:00)
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_conv_result = await db.execute(
        select(func.count())
        .select_from(ConversationHistory)
        .where(ConversationHistory.created_at >= today_start)
    )
    today_conversations = today_conv_result.scalar() or 0

    # 评论总数
    total_comments_result = await db.execute(select(func.count()).select_from(Comment))
    total_comments = total_comments_result.scalar() or 0

    # 有效邀请码数 (expiry_time > now)
    now = datetime.now()
    active_codes_result = await db.execute(
        select(func.count())
        .select_from(InviteCode)
        .where(InviteCode.expiry_time > now)
    )
    active_invite_codes = active_codes_result.scalar() or 0

    return {
        "total_users": total_users,
        "today_conversations": today_conversations,
        "total_comments": total_comments,
        "active_invite_codes": active_invite_codes,
    }


def generate_single_invite_code() -> str:
    """
    生成一个8位随机邀请码，由数字、大写字母、小写字母随机组成。
    移植自 create_invite_code.sql 的 CONCAT + ELT 逻辑。
    """
    chars_pool = [
        string.digits,  # 0-9
        string.ascii_uppercase,  # A-Z
        string.ascii_lowercase  # a-z
    ]
    code = []
    for _ in range(8):
        pool = random.choice(chars_pool)
        code.append(random.choice(pool))
    return ''.join(code)


async def batch_create_invite_codes(
        db: AsyncSession,
        count: int,
        expiry_days: int
) -> tuple[List[str], datetime]:
    """
    批量生成邀请码，并写入数据库。
    返回: (生成的邀请码列表, 统一的过期时间)
    """
    expiry_time = datetime.now() + timedelta(days=expiry_days)
    codes = []

    # 为了保证唯一性，使用循环直到生成指定数量的不重复码
    # 由于字符空间足够大，碰撞概率极低，简单处理即可
    for _ in range(count):
        while True:
            code = generate_single_invite_code()
            # 检查是否已存在（未过期或已过期都算存在）
            stmt = select(InviteCode).where(InviteCode.code == code)
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()
            if not existing:
                break
        # 创建新记录
        invite = InviteCode(code=code, expiry_time=expiry_time)
        db.add(invite)
        codes.append(code)

    await db.flush()  # 确保插入成功，但事务由上层提交
    return codes, expiry_time


async def get_admin_logs_cursor_paginated(
        db: AsyncSession,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        cursor_created_at: Optional[datetime] = None,
        cursor_id: Optional[int] = None,
        page_size: int = 20
) -> Tuple[List[AdminLog], Optional[Tuple[datetime, int]]]:
    """
    游标分页查询 admin_logs，按 (created_at DESC, id DESC) 排序。
    支持按日期范围过滤。
    返回 (日志列表, 下一页游标(created_at, id) 或 None)
    """
    # 基础查询条件
    conditions = []
    if start_date:
        conditions.append(AdminLog.created_at >= start_date)
    if end_date:
        # 结束日期通常包含整天，所以用 < 第二天
        next_day = end_date + timedelta(days=1)
        conditions.append(AdminLog.created_at < next_day)

    # 游标条件：对于倒序分页，需要 created_at < cursor_created_at 或者 created_at 相等时 id < cursor_id
    if cursor_created_at is not None and cursor_id is not None:
        conditions.append(
            tuple_(AdminLog.created_at, AdminLog.id) < (cursor_created_at, cursor_id)
        )

    # 构建查询
    stmt = select(AdminLog).order_by(AdminLog.created_at.desc(), AdminLog.id.desc())
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.limit(page_size + 1)  # 多取一条用于判断 has_more

    result = await db.execute(stmt)
    logs = result.scalars().all()

    has_more = len(logs) > page_size
    if has_more:
        logs = logs[:page_size]
        last_log = logs[-1]
        next_cursor = (last_log.created_at, last_log.id)
    else:
        next_cursor = None

    return logs, next_cursor


async def disable_admin_login(db: AsyncSession) -> bool:
    """
    将 system_config 表中的 admin_login_enabled 设为 false。
    返回 True 表示成功更新，若配置项不存在返回 False（理论上初始化已存在）。
    """
    stmt = (
        sql_update(SystemConfig)
        .where(SystemConfig.config_key == "admin_login_enabled")
        .values(config_value="false", updated_at=datetime.now())
    )
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount > 0


async def get_users_paginated(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20
) -> Tuple[List[Dict[str, Any]], int]:
    """分页返回用户列表，包含五维状态、事件数、对话数（仅 user 角色）"""
    from models import UserStatus, Event

    # 计数子查询
    event_count_sub = (
        select(func.count(Event.id))
        .where(Event.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    conv_count_sub = (
        select(func.count(ConversationHistory.id))
        .where(
            ConversationHistory.user_id == User.id,
            ConversationHistory.role == 'user'
        )
        .correlate(User)
        .scalar_subquery()
    )

    # 总数
    total_stmt = select(func.count()).select_from(User)
    total_res = await db.execute(total_stmt)
    total = total_res.scalar() or 0

    # 分页数据
    offset = (page - 1) * page_size
    stmt = (
        select(
            User.id,
            User.phone,
            User.nickname,
            User.invite_code,
            User.created_at,
            User.can_login,
            UserStatus.psychological_harmony_index,
            event_count_sub.label("event_count"),
            conv_count_sub.label("conversation_count"),
        )
        .outerjoin(UserStatus, User.id == UserStatus.user_id)
        .order_by(User.created_at.desc(), User.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    rows = result.all()

    # 字典列表
    users = [
        {
            "id": row.id,
            "phone": row.phone,
            "nickname": row.nickname,
            "invite_code": row.invite_code,
            "created_at": row.created_at,
            "can_login": row.can_login,
            "psychological_harmony_index": row.psychological_harmony_index,
            "event_count": row.event_count,
            "conversation_count": row.conversation_count,
        }
        for row in rows
    ]
    return users, total


async def get_comments_paginated(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20
) -> Tuple[List[Comment], int]:
    """分页返回所有评论（按时间倒序）"""
    total_stmt = select(func.count()).select_from(Comment)
    total_res = await db.execute(total_stmt)
    total = total_res.scalar() or 0

    offset = (page - 1) * page_size
    stmt = (
        select(Comment)
        .order_by(Comment.created_at.desc(), Comment.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    comments = result.scalars().all()
    return list(comments), total


async def get_invite_codes_paginated(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20
) -> Tuple[List[InviteCode], int]:
    """分页返回所有邀请码（按过期时间倒序，id 倒序）"""
    total_stmt = select(func.count()).select_from(InviteCode)
    total_res = await db.execute(total_stmt)
    total = total_res.scalar() or 0

    offset = (page - 1) * page_size
    stmt = (
        select(InviteCode)
        .order_by(InviteCode.expiry_time.desc(), InviteCode.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    codes = result.scalars().all()
    return list(codes), total


async def get_admin_logs_all_paginated(
        db: AsyncSession,
        page: int = 1,
        page_size: int = 20
) -> Tuple[List[AdminLog], int]:
    """分页返回所有管理员操作日志（全量，按时间倒序）"""
    total_stmt = select(func.count()).select_from(AdminLog)
    total_res = await db.execute(total_stmt)
    total = total_res.scalar() or 0

    offset = (page - 1) * page_size
    stmt = (
        select(AdminLog)
        .order_by(AdminLog.created_at.desc(), AdminLog.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    logs = result.scalars().all()
    return list(logs), total


# 单个记录查询（用于快照）
async def get_user_by_id_admin(db: AsyncSession, user_id: int):
    return await db.get(User, user_id)


async def get_comment_by_id(db: AsyncSession, comment_id: int):
    return await db.get(Comment, comment_id)


async def get_invite_code_by_id(db: AsyncSession, invite_id: int):
    return await db.get(InviteCode, invite_id)


# 更新操作
async def update_user_admin(db: AsyncSession, user_id: int, phone: str, nickname: str, can_login: bool):
    stmt = (
        sql_update(User)
        .where(User.id == user_id)
        .values(phone=phone, nickname=nickname, can_login=can_login, updated_at=datetime.now())
    )
    await db.execute(stmt)
    await db.flush()


async def update_comment_admin(db: AsyncSession, comment_id: int, content: str, replied: bool):
    stmt = (
        sql_update(Comment)
        .where(Comment.id == comment_id)
        .values(content=content, replied=replied)
    )
    await db.execute(stmt)
    await db.flush()


async def update_invite_code_admin(db: AsyncSession, invite_id: int, code: str, expiry_time: datetime):
    stmt = (
        sql_update(InviteCode)
        .where(InviteCode.id == invite_id)
        .values(code=code, expiry_time=expiry_time)
    )
    await db.execute(stmt)
    await db.flush()


# 删除操作
async def delete_user_admin(db: AsyncSession, user_id: int):
    stmt = sql_delete(User).where(User.id == user_id)
    await db.execute(stmt)
    await db.flush()


async def delete_comment_admin(db: AsyncSession, comment_id: int):
    stmt = sql_delete(Comment).where(Comment.id == comment_id)
    await db.execute(stmt)
    await db.flush()


async def delete_invite_code_admin(db: AsyncSession, invite_id: int):
    stmt = sql_delete(InviteCode).where(InviteCode.id == invite_id)
    await db.execute(stmt)
    await db.flush()


async def delete_admin_log_by_id(db: AsyncSession, log_id: int):
    stmt = sql_delete(AdminLog).where(AdminLog.id == log_id)
    await db.execute(stmt)
    await db.flush()
