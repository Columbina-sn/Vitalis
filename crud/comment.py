# crud/comment.py
from typing import Optional, Tuple, List, Dict, Any

from sqlalchemy import select, func, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from models import Comment
from datetime import datetime


async def get_comments_cursor_paginated(
    db: AsyncSession,
    limit: int = 10,
    cursor_is_long: Optional[bool] = None,
    cursor_created_at: Optional[datetime] = None,
    cursor_id: Optional[int] = None,
) -> Tuple[List[Comment], Dict[str, Any]]:
    """
    基于游标的分页查询评论列表。
    排序规则：is_long DESC, created_at DESC, id DESC
    返回：(评论列表, next_cursor 字典或 None)
    """
    # 构建基础查询并排序
    stmt = select(Comment).order_by(
        (func.length(Comment.content) > 50).desc(),  # is_long
        Comment.created_at.desc(),
        Comment.id.desc()
    )

    # 如果有游标，添加 WHERE 条件： (is_long, created_at, id) < (cursor...)
    if cursor_is_long is not None and cursor_created_at is not None and cursor_id is not None:
        # 注意：SQLAlchemy 的 tuple_ 比较需要三个字段一一对应
        stmt = stmt.where(
            tuple_(
                (func.length(Comment.content) > 50),
                Comment.created_at,
                Comment.id
            ) < (cursor_is_long, cursor_created_at, cursor_id)
        )

    # 多取一条用于判断 has_more
    stmt = stmt.limit(limit + 1)
    result = await db.execute(stmt)
    items = result.scalars().all()

    has_more = len(items) > limit
    if has_more:
        items = items[:limit]

    # 构建下一页游标（取最后一条记录的信息）
    next_cursor = None
    if has_more and items:
        last = items[-1]
        next_cursor = {
            "is_long": len(last.content) > 50,
            "created_at": last.created_at.isoformat(),
            "id": last.id
        }

    return items, next_cursor


async def get_comments_list(db: AsyncSession, skip: int = 0, limit: int = 10):
    """
    获取评论列表
    排序规则：
        1. 优先显示内容长度 > 50 的评论
        2. 按创建时间倒序（新评论在前）
    """
    stmt = (
        select(Comment)
        .order_by(
            (func.length(Comment.content) > 50).desc(),  # 字数>50的优先
            Comment.created_at.desc()            # 新评论优先
        )
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


async def get_total_comments_count(db: AsyncSession):
    """获取评论数量"""
    stmt = select(func.count(Comment.id))
    result = await db.execute(stmt)
    return result.scalar_one()  # 只能有1个结果 否则报错


async def add_new_comment(db: AsyncSession, content: str, ip: str):
    """添加评论（需外部调用频率检查）"""
    comment = Comment(content=content, ip_address=ip)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


async def get_comment_count_by_ip(
    db: AsyncSession,
    ip: str,
    since: datetime
):
    """查询某IP在指定时间后的评论数量"""
    stmt = select(func.count(Comment.id)).where(
        Comment.ip_address == ip,
        Comment.created_at > since
    )
    result = await db.execute(stmt)
    return result.scalar_one()