# crud/chat.py
from datetime import date as date_type
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

from sqlalchemy import select, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from models import (
    User, UserStatus, EmotionShift, ConversationHistory, RoleEnum,
    UserStatusHistory, MemoryAnchor, MemorySnapshot, UserSchedule
)
from utills.psychological_harmony_index import calculate_phi


async def get_user_full_info(
        db: AsyncSession, user_id: int
) -> Optional[Dict[str, Any]]:
    """
    获取用户的完整上下文信息：状态、近7天情绪转折（最多5条）、最近4条对话、
    长期记忆（近21天锚点按置信度取前8、近2天摘要1条、未来7天日程不限条数）。
    """
    user = await db.get(User, user_id)
    if not user:
        return None

    # 状态
    status_result = await db.execute(
        select(UserStatus).where(UserStatus.user_id == user_id)
    )
    status = status_result.scalar_one_or_none()

    # 近7天情绪转折（按创建时间倒序，最多取5条）
    seven_days_ago = datetime.now() - timedelta(days=7)
    events_result = await db.execute(
        select(EmotionShift)
        .where(EmotionShift.user_id == user_id, EmotionShift.created_at >= seven_days_ago)
        .order_by(desc(EmotionShift.created_at))
        .limit(5)
    )
    emotion_shifts = events_result.scalars().all()

    # 最近4条对话
    messages_result = await db.execute(
        select(ConversationHistory)
        .where(ConversationHistory.user_id == user_id)
        .order_by(desc(ConversationHistory.created_at))
        .limit(4)
    )
    recent_conversations = messages_result.scalars().all()

    # 长期记忆：近21天内更新的锚点，按置信度降序取前8
    three_weeks_ago = datetime.now() - timedelta(days=21)
    anchors_result = await db.execute(
        select(MemoryAnchor)
        .where(
            MemoryAnchor.user_id == user_id,
            MemoryAnchor.updated_at >= three_weeks_ago
        )
        .order_by(desc(MemoryAnchor.confidence))
        .limit(8)
    )
    anchors = anchors_result.scalars().all()

    # 近2天的记忆快照，最多1条
    two_days_ago = datetime.now() - timedelta(days=2)
    snapshots_result = await db.execute(
        select(MemorySnapshot)
        .where(MemorySnapshot.user_id == user_id, MemorySnapshot.created_at >= two_days_ago)
        .order_by(desc(MemorySnapshot.created_at))
        .limit(1)
    )
    snapshots = snapshots_result.scalars().all()

    # 未来7天内未完成的日程（不限条数）
    now = datetime.now()
    future_deadline = now + timedelta(days=7)
    schedules_result = await db.execute(
        select(UserSchedule)
        .where(
            UserSchedule.user_id == user_id,
            UserSchedule.is_completed == False,
            UserSchedule.scheduled_time >= now,
            UserSchedule.scheduled_time <= future_deadline
        )
        .order_by(UserSchedule.scheduled_time.asc())
    )
    upcoming_schedules = schedules_result.scalars().all()

    return {
        "status": status,
        "events": emotion_shifts,
        "recent_conversations": recent_conversations,
        "anchors": anchors,
        "snapshots": snapshots,
        "upcoming_schedules": upcoming_schedules,
    }


async def add_or_update_memory_anchor(
        db: AsyncSession,
        user_id: int,
        anchor_type: str,
        content: str,
        confidence: float = 0.5
) -> MemoryAnchor:
    """
    添加或更新用户画像锚点。若存在同类型且内容相似（完全相同）的锚点，
    则更新其内容、置信度和最后提及时间；否则创建新锚点。
    """
    # 查找是否存在同类型且内容完全相同的锚点
    result = await db.execute(
        select(MemoryAnchor).where(
            MemoryAnchor.user_id == user_id,
            MemoryAnchor.anchor_type == anchor_type,
            MemoryAnchor.content == content
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        existing.confidence = confidence
        existing.last_mentioned_at = datetime.now()
        existing.updated_at = datetime.now()
        return existing
    else:
        anchor = MemoryAnchor(
            user_id=user_id,
            anchor_type=anchor_type,
            content=content,
            confidence=confidence,
            last_mentioned_at=datetime.now()
        )
        db.add(anchor)
        await db.flush()
        return anchor


async def create_schedule(
        db: AsyncSession,
        user_id: int,
        schedule_type: str,
        title: str,
        description: Optional[str] = None,
        scheduled_time: Optional[datetime] = None,
        is_completed: bool = False
) -> UserSchedule:
    """创建日程"""
    schedule = UserSchedule(
        user_id=user_id,
        schedule_type=schedule_type,
        title=title,
        description=description,
        scheduled_time=scheduled_time,
        is_completed=is_completed
    )
    db.add(schedule)
    await db.flush()
    return schedule


async def check_recent_similar_schedule(
        db: AsyncSession,
        user_id: int,
        schedule_type: str,
        title: str,
        within_hours: int = 1
) -> bool:
    """检查最近一段时间内是否存在相同类型和标题的日程，防止重复创建"""
    since_time = datetime.now() - timedelta(hours=within_hours)
    result = await db.execute(
        select(UserSchedule).where(
            UserSchedule.user_id == user_id,
            UserSchedule.schedule_type == schedule_type,
            UserSchedule.title == title,
            UserSchedule.created_at >= since_time
        )
    )
    return result.scalar_one_or_none() is not None


async def check_recent_duplicate_emotion_shift(
        db: AsyncSession, user_id: int, detail: str, within_hours: int = 1
) -> bool:
    """检查最近一段时间内是否存在内容相同的情绪转折记录"""
    since_time = datetime.now() - timedelta(hours=within_hours)
    result = await db.execute(
        select(EmotionShift).where(
            EmotionShift.user_id == user_id,
            EmotionShift.emotion_change_detail == detail,
            EmotionShift.created_at >= since_time
        )
    )
    return result.scalar_one_or_none() is not None


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


async def add_emotion_shift(
        db: AsyncSession,
        user_id: int,
        emotion_change_detail: str,
        trigger_keywords: Optional[str] = None
) -> EmotionShift:
    """
    增加一条情绪转折记录

    Args:
        db: 数据库会话
        user_id: 用户 ID
        emotion_change_detail: 情绪变化的详细描述
        trigger_keywords: 触发该情绪转折的关键词（可选）

    Returns:
        创建的 EmotionShift 对象
    """
    shift = EmotionShift(
        user_id=user_id,
        emotion_change_detail=emotion_change_detail,
        trigger_keywords=trigger_keywords
    )
    db.add(shift)
    await db.flush()
    return shift


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