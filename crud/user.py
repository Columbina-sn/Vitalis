# crud/user.py
from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional

from models import User, UserStatus, InviteCode, UserStatusHistory, Event
from utills.psychological_harmony_index import calculate_phi
from utills.security import get_hash_password


async def get_user_by_phone(db: AsyncSession, phone: str) -> Optional[User]:
    """根据手机号查询用户"""
    result = await db.execute(select(User).where(User.phone == phone))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, phone: str, password: str, invite_code: str) -> User:
    """创建新用户（密码已加密）"""
    hashed_pwd = get_hash_password(password)
    user = User(
        phone=phone,
        password=hashed_pwd,
        invite_code=invite_code,
        nickname=None,  # 可选，后续可让用户完善
        avatar=None,
        has_seen_intro=False
    )
    db.add(user)
    await db.flush()  # 获得自增 id
    return user


async def create_user_status(db: AsyncSession, user_id: int) -> UserStatus:
    """为新用户创建默认五维状态（全 50）"""
    status = UserStatus(user_id=user_id)
    phi = calculate_phi(50, 50, 50, 50, 50)
    status.psychological_harmony_index = phi
    db.add(status)
    await db.flush()
    return status


async def get_valid_invite_code(db: AsyncSession, code: str) -> Optional[InviteCode]:
    """查询未过期的邀请码"""
    now = datetime.now()
    result = await db.execute(
        select(InviteCode).where(
            InviteCode.code == code,
            InviteCode.expiry_time > now
        )
    )
    return result.scalar_one_or_none()


async def delete_invite_code(db: AsyncSession, code: str) -> None:
    """删除已使用的邀请码（一次性使用）"""
    await db.execute(delete(InviteCode).where(InviteCode.code == code))


async def update_user_nickname(db: AsyncSession, user_id: int, new_nickname: str) -> User:
    """更新用户昵称"""
    user = await db.get(User, user_id)
    if user:
        user.nickname = new_nickname
        await db.flush()
    return user


async def update_user_avatar(db: AsyncSession, user_id: int, avatar_url: str) -> User:
    """更新用户头像URL"""
    user = await db.get(User, user_id)
    if user:
        user.avatar = avatar_url
        await db.flush()
    return user


async def get_user_info_by_id(db: AsyncSession, user_id: int) -> Optional[dict]:
    """根据用户ID获取用户信息（手机号、昵称、头像、邀请码）"""
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        return None
    return {
        "phone": user.phone,
        "nickname": user.nickname,
        "avatar": user.avatar,
        "invite_code": user.invite_code,
    }


async def delete_user_account(db: AsyncSession, user: User) -> None:
    """
    物理删除用户及其所有关联数据（依赖数据库外键级联删除）
    - 用户状态表 user_status (ON DELETE CASCADE)
    - 事件表 event (ON DELETE CASCADE)
    - 对话历史表 conversation_history (ON DELETE CASCADE)
    """
    await db.delete(user)
    await db.commit()


async def get_user_status_by_user_id(db: AsyncSession, user_id: int) -> Optional[UserStatus]:
    """根据用户ID获取用户状态记录"""
    result = await db.execute(
        select(UserStatus).where(UserStatus.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_recent_events_by_user_id(
    db: AsyncSession, user_id: int, limit: int = 3
) -> list[str]:
    """
    获取用户最近的事件概述（按创建时间倒序，限制条数）
    """
    from models import Event
    from sqlalchemy import desc

    result = await db.execute(
        select(Event.event_summary)
        .where(Event.user_id == user_id)
        .order_by(desc(Event.created_at))
        .limit(limit)
    )
    summaries = result.scalars().all()
    return list(summaries)


async def update_user_password(db: AsyncSession, user_id: int, hashed_password: str) -> Optional[User]:
    """更新用户密码（已哈希）"""
    user = await db.get(User, user_id)
    if user:
        user.password = hashed_password
        await db.flush()
    return user


async def get_status_history_by_dimension(
    db: AsyncSession,
    user_id: int,
    dimension: str,
    limit: int = 10
) -> list[dict]:
    """
    获取用户某个维度的状态历史数据（按 recorded_at 降序）
    返回包含 recorded_at 和对应维度值的字典列表
    """
    # 动态获取模型中的字段（确保 dimension 安全）
    if not hasattr(UserStatusHistory, dimension):
        raise ValueError(f"Invalid dimension: {dimension}")

    dimension_column = getattr(UserStatusHistory, dimension)

    stmt = (
        select(
            UserStatusHistory.recorded_at,
            dimension_column.label("value")
        )
        .where(UserStatusHistory.user_id == user_id)
        .order_by(desc(UserStatusHistory.recorded_at))
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [{"recorded_at": row.recorded_at, "value": row.value} for row in rows]


# crud/user.py
async def get_user_export_data_html(db: AsyncSession, user_id: int) -> dict:
    """获取用于HTML导出的数据（不含对话历史）"""
    user = await db.get(User, user_id)
    if not user:
        return None

    user_info = {
        "phone": user.phone,
        "nickname": user.nickname or "未设置",
        "avatar": user.avatar,
        "invite_code": user.invite_code or "无",
        "created_at": user.created_at.strftime("%Y年%m月%d日 %H:%M") if user.created_at else "未知",
    }

    status_obj = await db.get(UserStatus, user_id)
    status_data = None
    if status_obj:
        status_data = {
            "physical": status_obj.physical_vitality,
            "emotional": status_obj.emotional_tone,
            "relation": status_obj.relationship_connection,
            "worth": status_obj.self_worth,
            "meaning": status_obj.meaning_direction,
            "phi": status_obj.psychological_harmony_index,
            "updated": status_obj.updated_at.strftime("%Y年%m月%d日 %H:%M"),
        }

    events_result = await db.execute(
        select(Event)
        .where(Event.user_id == user_id)
        .order_by(Event.created_at.desc())
    )
    events = events_result.scalars().all()
    events_data = []
    for e in events:
        events_data.append({
            "summary": e.event_summary,
            "evaluation": e.initial_evaluation or "无评价",
            "time": e.created_at.strftime("%Y年%m月%d日 %H:%M"),
        })

    return {
        "user": user_info,
        "status": status_data,
        "events": events_data,
        "export_time": datetime.now().strftime("%Y年%m月%d日 %H:%M:%S"),
    }