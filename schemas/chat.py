# schemas/chat.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from models import RoleEnum


class ChatRequest(BaseModel):
    message: str = Field(default="", description="用户发送的消息，空字符串表示问候请求")


class ConversationHistoryResponse(BaseModel):
    """单条对话记录响应体"""
    id: int
    role: RoleEnum          # 角色：user / assistant
    content: str            # 对话内容
    created_at: datetime    # 创建时间
    # extra_metadata: Optional[dict] = None   # 附加元数据（若有）

    class Config:
        from_attributes = True   # 允许从 ORM 模型转换（Pydantic v2 写法）