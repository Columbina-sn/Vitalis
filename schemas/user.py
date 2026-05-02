# schemas/user.py
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List
import re


class UserCreate(BaseModel):
    """注册请求体"""
    phone: str = Field(..., min_length=11, max_length=15, description="手机号")
    password: str = Field(..., min_length=6, max_length=20, description="密码")
    invite_code: str = Field(..., min_length=8, max_length=8, description="8位邀请码")

    @field_validator("phone")
    def validate_phone(cls, v: str) -> str:
        if not re.match(r"^1[3-9]\d{9}$", v):
            raise ValueError("手机号格式不正确")
        return v


class UserLogin(BaseModel):
    """登录请求体"""
    phone: str = Field(..., description="手机号")
    password: str = Field(..., description="密码")


class Token(BaseModel):
    """Token 响应体"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token 中存储的数据（用于依赖注入）"""
    phone: Optional[str] = None


class UserBaseInfoResponse(BaseModel):
    """基本信息响应（/base-info）"""
    has_seen_intro: bool
    avatar: str


class UserInfoResponse(BaseModel):
    """用户所有信息响应（/information）"""
    phone: str
    nickname: Optional[str] = None
    avatar: str
    invite_code: Optional[str] = None

    class Config:
        from_attributes = True


class UpdateNicknameRequest(BaseModel):
    nickname: str = Field(..., min_length=1, max_length=15, description="新昵称")


class UpdateAvatarResponse(BaseModel):
    avatar_url: str


class DeleteAccountRequest(BaseModel):
    """注销账户请求体"""
    password: str = Field(..., min_length=6, max_length=20, description="密码，用于验证身份")


class UserStatusResponse(BaseModel):
    """用户五维状态响应"""
    physical_vitality: int = Field(..., description="身心活力 0-100")
    emotional_tone: int = Field(..., description="情绪基调 0-100")
    relationship_connection: int = Field(..., description="关系联结 0-100")
    self_worth: int = Field(..., description="自我价值 0-100")
    meaning_direction: int = Field(..., description="意义方向 0-100")
    psychological_harmony_index: int = Field(..., description="心理和谐指数 1-100")

    class Config:
        from_attributes = True


# class RecentEventsResponse(BaseModel):
#     """最近重大事件响应"""
#     events: List[str] = Field(default_factory=list, description="事件概述列表（按时间倒序）")


class ChangePasswordRequest(BaseModel):
    """修改密码请求体"""
    old_password: str = Field(..., min_length=6, max_length=20, description="旧密码")
    new_password: str = Field(..., min_length=6, max_length=20, description="新密码")

    @field_validator("new_password")
    def validate_new_password(cls, v: str) -> str:
        # 获取旧密码的值需要额外处理，这里只做长度和简单校验
        if len(v) < 6:
            raise ValueError("新密码长度不能少于6位")
        # 注意：不能在这里直接比较 old_password，因为 old_password 在 info.data 中可能尚未验证
        return v

    @model_validator(mode="after")
    def check_passwords_different(self) -> "ChangePasswordRequest":
        if self.old_password == self.new_password:
            raise ValueError("新密码不能与旧密码相同")
        return self


# 定义允许的状态维度名称
class StatusDimension(str, Enum):
    PHYSICAL_VITALITY = "physical_vitality"
    EMOTIONAL_TONE = "emotional_tone"
    RELATIONSHIP_CONNECTION = "relationship_connection"
    SELF_WORTH = "self_worth"
    MEANING_DIRECTION = "meaning_direction"
    PSYCHOLOGICAL_HARMONY_INDEX = "psychological_harmony_index"


# 单条历史数据响应
class StatusHistoryItem(BaseModel):
    recorded_at: datetime
    value: int

    class Config:
        from_attributes = True


# 历史数据列表响应
class StatusHistoryResponse(BaseModel):
    dimension: StatusDimension
    history: List[StatusHistoryItem]


class ScheduleItem(BaseModel):
    id: int
    schedule_type: str
    title: str
    description: Optional[str] = None
    scheduled_time: Optional[str] = None  # ISO 格式字符串
    is_completed: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UserScheduleResponse(BaseModel):
    uncompleted: List[ScheduleItem]
    completed: List[ScheduleItem]