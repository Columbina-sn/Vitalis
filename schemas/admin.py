# schemas/admin.py
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator


class AdminSecondVerifyRequest(BaseModel):
    phone: str = Field(..., description="管理员手机号")
    second_password: str = Field(..., description="二级密码")


class AdminSecondVerifyResponseData(BaseModel):
    """管理员二级验证通过后的返回数据"""
    access_token: str = Field(..., description="管理员 JWT Token")
    token_type: str = Field(default="bearer", description="Token 类型")
    admin_redirect_url: str = Field(..., description="管理后台跳转地址（随机路径）")


class AdminStatsResponse(BaseModel):
    total_users: int
    today_conversations: int
    total_comments: int
    active_invite_codes: int


class BatchInviteCodeRequest(BaseModel):
    count: int = Field(..., ge=1, le=100, description="生成数量，1-100")
    expiry_days: int = Field(..., ge=1, le=7, description="有效期天数，1-7")

    @field_validator('expiry_days')
    def validate_expiry_days(cls, v):
        if v < 1 or v > 7:
            raise ValueError('有效期天数必须在1-7之间')
        return v


class BatchInviteCodeResponse(BaseModel):
    codes: list[str] = Field(..., description="生成的邀请码列表")
    expiry_time: str = Field(..., description="过期时间（ISO格式）")


class AdminLogItem(BaseModel):
    id: int
    admin_phone: str
    action_type: str
    remark: Optional[str] = None
    created_at: datetime


class AdminLogCursor(BaseModel):
    created_at: datetime
    id: int


class AdminLogsResponse(BaseModel):
    list: List[AdminLogItem]
    next_cursor: Optional[AdminLogCursor] = None


class UserInAdminList(BaseModel):
    id: int
    phone: str
    nickname: Optional[str] = None
    invite_code: Optional[str] = None
    created_at: datetime
    psychological_harmony_index: int
    conversation_count: int
    can_login: bool


class AdminUserListResponse(BaseModel):
    total: int
    list: List[UserInAdminList]


class UpdateUserRequest(BaseModel):
    phone: str = Field(..., min_length=11, max_length=11)
    nickname: Optional[str] = Field(None, min_length=1, max_length=15)
    can_login: bool


class CommentInAdminList(BaseModel):
    id: int
    content: str
    ip_address: str
    replied: bool
    created_at: datetime


class AdminCommentListResponse(BaseModel):
    total: int
    list: List[CommentInAdminList]


class UpdateCommentRequest(BaseModel):
    content: str = Field(..., min_length=1)
    replied: bool


class InviteCodeItem(BaseModel):
    id: int
    code: str
    expiry_time: datetime


class AdminInviteCodeListResponse(BaseModel):
    total: int
    list: List[InviteCodeItem]


class UpdateInviteCodeRequest(BaseModel):
    code: str = Field(..., min_length=8, max_length=8)
    expiry_time: datetime


class AdminLogItemFull(BaseModel):
    id: int
    admin_phone: str
    action_type: str
    remark: Optional[str] = None
    created_at: datetime


class AdminLogListResponse(BaseModel):
    total: int
    list: List[AdminLogItemFull]