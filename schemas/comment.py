# schemas/comment.py
from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    """发表评论的请求体"""
    content: str = Field(..., min_length=1, description="评论内容")