# crud/chat.py
from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models import User, UserStatus, Event, ConversationHistory, RoleEnum, UserStatusHistory
from utills.psychological_harmony_index import calculate_phi


async def get_user_full_info(
    db: AsyncSession, user_id: int
) -> Optional[Dict[str, Any]]:
    """
    获取用户的完整信息：状态、近7天内的重大事件、最近10条用户的对话内容
    Args:
        db: 数据库会话
        user_id: 用户 ID
    Returns:
        包含 status, events, recent_user_messages 的字典；如果用户不存在则返回 None
    """
    # 1. 检查用户是否存在
    user = await db.get(User, user_id)
    if not user:
        return None

    # 2. 获取用户状态（user_status 表，一对一）
    status_result = await db.execute(
        select(UserStatus).where(UserStatus.user_id == user_id)
    )
    status = status_result.scalar_one_or_none()

    # 3. 获取近7天内的重大事件（按创建时间倒序）
    ninety_days_ago = datetime.now() - timedelta(days=7)
    events_result = await db.execute(
        select(Event)
        .where(Event.user_id == user_id, Event.created_at >= ninety_days_ago)
        .order_by(desc(Event.created_at))
    )
    events = events_result.scalars().all()

    # 4. 获取最近10条用户对话
    messages_result = await db.execute(
        select(ConversationHistory)
        .where(ConversationHistory.user_id == user_id)
        .order_by(desc(ConversationHistory.created_at))
        .limit(10)
    )
    recent_conversations = messages_result.scalars().all()

    return {
        "status": status,
        "events": events,
        "recent_conversations": recent_conversations,
    }


async def update_user_status(
        db: AsyncSession, user_id: int, new_values: Dict[str, int]
) -> Optional[UserStatus]:
    """
    直接设置用户五维状态数值（最终值，0-100），并自动记录历史快照

    Args:
        db: 数据库会话
        user_id: 用户 ID
        new_values: 包含需要设置的维度和最终值，例如 {"physical_vitality": 55, "emotional_tone": 48}

    Returns:
        更新后的 UserStatus 对象，若用户状态不存在则返回 None
    """
    status = await db.get(UserStatus, user_id)
    if not status:
        return None

    fields = ["physical_vitality", "emotional_tone", "relationship_connection", "self_worth", "meaning_direction"]
    for field in fields:
        if field in new_values:
            val = new_values[field]
            # 限制范围 0-100
            val = max(0, min(100, val))
            setattr(status, field, val)

    phi = calculate_phi(
        status.physical_vitality,
        status.emotional_tone,
        status.relationship_connection,
        status.self_worth,
        status.meaning_direction,
    )
    status.psychological_harmony_index = phi

    # 插入历史快照
    history = UserStatusHistory(
        user_id=user_id,
        physical_vitality=status.physical_vitality,
        emotional_tone=status.emotional_tone,
        relationship_connection=status.relationship_connection,
        self_worth=status.self_worth,
        meaning_direction=status.meaning_direction,
        psychological_harmony_index=status.psychological_harmony_index,
        recorded_at=datetime.now(),
    )
    db.add(history)

    await db.flush()  # 同时刷新状态更新和历史插入
    return status


async def add_event(
    db: AsyncSession,
    user_id: int,
    event_summary: str,
    initial_evaluation: Optional[str] = None
) -> Event:
    """
    增加一条重大事件记录

    Args:
        db: 数据库会话
        user_id: 用户 ID
        event_summary: 事件概述（最长100字符）
        initial_evaluation: 初步评价（可选，最长100字符）

    Returns:
        创建的 Event 对象
    """
    event = Event(
        user_id=user_id,
        event_summary=event_summary[:100],
        initial_evaluation=initial_evaluation
    )
    db.add(event)
    await db.flush()
    return event


async def add_conversation_history(
    db: AsyncSession,
    user_id: int,
    role: RoleEnum,
    content: str,
    extra_metadata: Optional[dict] = None
) -> ConversationHistory:
    """
    增加一条对话历史记录

    Args:
        db: 数据库会话
        user_id: 用户 ID
        role: 消息角色（user 或 assistant）
        content: 消息文本内容
        extra_metadata: 附加元数据（可选，JSON格式）

    Returns:
        创建的 ConversationHistory 对象
    """
    history = ConversationHistory(
        user_id=user_id,
        role=role,
        content=content,
        extra_metadata=extra_metadata
    )
    db.add(history)
    await db.flush()
    return history


async def get_conversations_cursor_paginated(
        db: AsyncSession,
        user_id: int,
        before_id: Optional[int] = None,
        limit: int = 10
) -> Tuple[list[ConversationHistory], bool]:
    """
    基于游标的分页查询（使用自增ID，保证顺序唯一性）
    返回：(消息列表, 是否还有更多数据)
    """
    query = select(ConversationHistory).where(
        ConversationHistory.user_id == user_id
    )

    if before_id is not None:
        query = query.where(ConversationHistory.id < before_id)

    query = query.order_by(desc(ConversationHistory.id)).limit(limit + 1)  # 多取一条判断has_more

    result = await db.execute(query)
    items = result.scalars().all()

    has_more = len(items) > limit
    if has_more:
        items = items[:limit]

    return items, has_more


async def get_conversations_by_date(
    db: AsyncSession,
    user_id: int,
    target_date: date_type
) -> list[ConversationHistory]:
    """
    获取指定用户在某一天的所有对话历史（按时间正序排列）

    Args:
        db: 数据库会话
        user_id: 用户 ID
        target_date: 目标日期（date 对象）

    Returns:
        对话记录列表，按 created_at 升序排列
    """
    # 将日期转换为当天的起始和结束时间戳（naive datetime，与数据库一致）
    start_dt = datetime.combine(target_date, datetime.min.time())
    end_dt = datetime.combine(target_date, datetime.max.time())

    query = (
        select(ConversationHistory)
        .where(
            and_(
                ConversationHistory.user_id == user_id,
                ConversationHistory.created_at >= start_dt,
                ConversationHistory.created_at <= end_dt
            )
        )
        .order_by(ConversationHistory.created_at.asc())
    )

    result = await db.execute(query)
    return result.scalars().all()