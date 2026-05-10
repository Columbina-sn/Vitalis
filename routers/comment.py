# routers/comment.py
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import os

from config.db_conf import get_db
from crud import comment
from schemas.comment import CommentCreate
from utills.ip_utils import get_client_ip
from utills.response import success_response
from utills.logging_conf import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/comment", tags=["评论"])

# 从环境变量读取频率限制，默认值 1 和 5
RATE_LIMIT_PER_MINUTE = int(os.getenv("COMMENT_RATE_LIMIT_PER_MINUTE", "1"))
RATE_LIMIT_PER_HOUR = int(os.getenv("COMMENT_RATE_LIMIT_PER_HOUR", "5"))


@router.get("/list", summary="游标分页获取评论")
async def get_comments(
    page_size: int = Query(10, ge=1, le=20, alias="pageSize"),
    cursor_is_long: Optional[bool] = Query(None),
    cursor_created_at: Optional[str] = Query(None),
    cursor_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    基于游标的分页获取评论列表。
    首次请求不传游标参数，后续请求传入上次返回的 nextCursor。
    """
    # 解析时间字符串
    parsed_created_at = None
    if cursor_created_at:
        try:
            parsed_created_at = datetime.fromisoformat(cursor_created_at)
        except ValueError:
            raise HTTPException(status_code=400, detail="cursor_created_at 格式错误")

    comments, next_cursor = await comment.get_comments_cursor_paginated(
        db,
        limit=page_size,
        cursor_is_long=cursor_is_long,
        cursor_created_at=parsed_created_at,
        cursor_id=cursor_id,
    )

    # 注意：返回的 Comment 是 ORM 对象，需要转换为字典或由 Pydantic 序列化
    # 假设已有 CommentResponse schema，若无则可直接返回 list
    response_data = {
        "list": comments,  # 如果前端期望直接拿到对象，FastAPI 会自动序列化
        "nextCursor": next_cursor,
    }
    return success_response(message="获取评论列表成功", data=response_data)


@router.post("/new-comment", summary="发送评论")
async def post_new_comment(
    request: Request,
    data: CommentCreate,
    db: AsyncSession = Depends(get_db)
):
    # 使用封装的函数获取真实 IP
    client_ip = get_client_ip(request)

    now = datetime.now()
    one_minute_ago = now - timedelta(minutes=1)
    one_hour_ago = now - timedelta(hours=1)

    minute_count = await comment.get_comment_count_by_ip(db, client_ip, one_minute_ago)
    if minute_count >= RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="评论过于频繁，请稍后再试")

    hour_count = await comment.get_comment_count_by_ip(db, client_ip, one_hour_ago)
    if hour_count >= RATE_LIMIT_PER_HOUR:
        raise HTTPException(status_code=429, detail="每小时最多发表5条评论")

    result = await comment.add_new_comment(db, data.content, client_ip)
    logger.info(f"新评论来自 IP {client_ip}")
    return success_response(message="添加评论成功", data=result)