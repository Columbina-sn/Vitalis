# models.py
from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, SmallInteger, Boolean, ForeignKey, Index, CheckConstraint, Integer
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy import BigInteger, Text, JSON, Enum as SQLEnum, TIMESTAMP
import enum


class Base(DeclarativeBase):
    pass


class RoleEnum(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class User(Base):
    __tablename__ = 'users'

    __table_args__ = (
        # 手机号唯一索引（对应 SQL 中的 uk_phone）
        Index('uk_phone', 'phone', unique=True),
        # 邀请码普通索引
        Index('idx_invite_code', 'invite_code'),
        Index('idx_users_created_at', 'created_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    phone: Mapped[str] = mapped_column(String(15), nullable=False, comment="手机号")
    password: Mapped[str] = mapped_column(String(64), nullable=False, comment="登录密码")
    nickname: Mapped[Optional[str]] = mapped_column(String(15), comment="昵称")
    avatar: Mapped[Optional[str]] = mapped_column(String(500), default='/static_pic/default_avatar.jpg', comment="头像URL")
    has_seen_intro: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否已看过引导介绍")
    can_login: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否允许登录")
    invite_code: Mapped[Optional[str]] = mapped_column(String(15), comment="用户注册时使用的邀请码")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return f"<User(id={self.id}, phone='{self.phone}', nickname='{self.nickname}')>"


class UserStatus(Base):
    __tablename__ = 'user_status'

    __table_args__ = (
        # 五维指标的值域约束 0-100
        CheckConstraint('physical_vitality BETWEEN 0 AND 100', name='chk_physical_vitality'),
        CheckConstraint('emotional_tone BETWEEN 0 AND 100', name='chk_emotional_tone'),
        CheckConstraint('relationship_connection BETWEEN 0 AND 100', name='chk_relationship_connection'),
        CheckConstraint('self_worth BETWEEN 0 AND 100', name='chk_self_worth'),
        CheckConstraint('meaning_direction BETWEEN 0 AND 100', name='chk_meaning_direction'),
        CheckConstraint('psychological_harmony_index BETWEEN 1 AND 100', name='chk_psychological_harmony_index'),
    )

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('users.id', ondelete='CASCADE', onupdate='CASCADE'),
        primary_key=True,
        comment="用户ID（主键，关联users表）"
    )
    physical_vitality: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=50, comment="身心活力（0-100）")
    emotional_tone: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=50, comment="情绪基调（0-100）")
    relationship_connection: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=50, comment="关系联结（0-100）")
    self_worth: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=50, comment="自我价值（0-100）")
    meaning_direction: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=50, comment="意义方向（0-100）")
    psychological_harmony_index: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=63, comment="心理和谐指数（1-100）"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return f"<UserStatus(user_id={self.user_id}, physical_vitality={self.physical_vitality}, ...)>"


class Event(Base):
    __tablename__ = 'event'

    __table_args__ = (
        Index('idx_user_id', 'user_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="事件主键ID")
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('users.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False,
        comment="所属用户ID"
    )
    event_summary: Mapped[str] = mapped_column(String(100), nullable=False, comment="事件概述")
    initial_evaluation: Mapped[Optional[str]] = mapped_column(String(100), comment="初步评价")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return f"<Event(id={self.id}, user_id={self.user_id}, summary='{self.event_summary}')>"


class InviteCode(Base):
    __tablename__ = 'invite_code'

    __table_args__ = (
        Index('uk_code', 'code', unique=True),
        Index('idx_expiry_time', 'expiry_time'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    code: Mapped[str] = mapped_column(String(15), nullable=False, comment="邀请码")
    expiry_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="过期时间")

    def __repr__(self):
        return f"<InviteCode(id={self.id}, code='{self.code}', expiry={self.expiry_time})>"


class ConversationHistory(Base):
    __tablename__ = 'conversation_history'

    __table_args__ = (
        Index('idx_user_time', 'user_id', 'created_at'),
        Index('idx_user_role_time', 'user_id', 'role', 'created_at'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="对话记录主键ID")
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('users.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False,
        comment="所属用户ID"
    )
    role: Mapped[RoleEnum] = mapped_column(SQLEnum(RoleEnum), nullable=False, comment="消息角色")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息文本内容")
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSON, name="metadata", nullable=True, comment="附加元数据")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.now, comment="创建时间")

    def __repr__(self):
        return f"<ConversationHistory(id={self.id}, user_id={self.user_id}, role='{self.role.value}')>"


class Comment(Base):
    __tablename__ = 'comment'

    __table_args__ = (
        Index('idx_ip_time', 'ip_address', 'created_at'),  # 联合索引，用于频率限制查询
        Index('idx_comment_created_at', 'created_at'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="评论主键ID")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="评论内容")
    ip_address: Mapped[str] = mapped_column(String(45), nullable=False, index=True, comment="评论者IP地址")
    replied: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, comment="是否已回复")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, default=datetime.now, comment="创建时间")

    def __repr__(self):
        return f"<Comment(id={self.id}, content='{self.content[:20]}...', created_at='{self.created_at}')>"


class UserStatusHistory(Base):
    __tablename__ = 'user_status_history'

    __table_args__ = (
        # 五维指标的值域约束 0-100
        CheckConstraint('physical_vitality BETWEEN 0 AND 100', name='chk_history_physical_vitality'),
        CheckConstraint('emotional_tone BETWEEN 0 AND 100', name='chk_history_emotional_tone'),
        CheckConstraint('relationship_connection BETWEEN 0 AND 100', name='chk_history_relationship_connection'),
        CheckConstraint('self_worth BETWEEN 0 AND 100', name='chk_history_self_worth'),
        CheckConstraint('meaning_direction BETWEEN 0 AND 100', name='chk_history_meaning_direction'),
        CheckConstraint('psychological_harmony_index BETWEEN 1 AND 100',
                        name='chk_history_psychological_harmony_index'),
        # 用户+记录时间复合索引（便于按时间轴查询）
        Index('idx_user_recorded', 'user_id', 'recorded_at'),
        # 每个状态列单独索引（便于针对某一维度的统计分析）
        Index('idx_physical_vitality', 'physical_vitality'),
        Index('idx_emotional_tone', 'emotional_tone'),
        Index('idx_relationship_connection', 'relationship_connection'),
        Index('idx_self_worth', 'self_worth'),
        Index('idx_meaning_direction', 'meaning_direction'),
        Index('idx_psychological_harmony_index', 'psychological_harmony_index')
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="历史记录主键ID")
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey('users.id', ondelete='CASCADE', onupdate='CASCADE'),
        nullable=False,
        comment="用户ID"
    )
    physical_vitality: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment="身心活力（0-100）")
    emotional_tone: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment="情绪基调（0-100）")
    relationship_connection: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment="关系联结（0-100）")
    self_worth: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment="自我价值（0-100）")
    meaning_direction: Mapped[int] = mapped_column(SmallInteger, nullable=False, comment="意义方向（0-100）")
    psychological_harmony_index: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, comment="心理和谐指数（1-100）"
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="状态记录时间（即状态更新的时间点）")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="历史记录创建时间")

    def __repr__(self):
        return f"<UserStatusHistory(id={self.id}, user_id={self.user_id}, recorded_at={self.recorded_at})>"


class SystemConfig(Base):
    __tablename__ = 'system_config'

    __table_args__ = (
        Index('uk_config_key', 'config_key', unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="配置项主键ID")
    config_key: Mapped[str] = mapped_column(String(64), nullable=False, comment="配置键名（唯一）")
    config_value: Mapped[str] = mapped_column(Text, nullable=False, comment="配置值")
    description: Mapped[Optional[str]] = mapped_column(String(255), comment="配置项说明")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now, comment="更新时间")

    def __repr__(self):
        return f"<SystemConfig(key='{self.config_key}', value='{self.config_value}')>"


class AdminLog(Base):
    __tablename__ = 'admin_logs'

    __table_args__ = (
        Index('idx_admin_phone', 'admin_phone'),
        Index('idx_action_type', 'action_type'),
        Index('idx_created_at', 'created_at'),
        Index('idx_target', 'target_table', 'target_id'),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="日志主键ID")
    admin_phone: Mapped[str] = mapped_column(String(15), nullable=False, comment="执行操作的管理员手机号")
    action_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="操作类型")
    target_table: Mapped[Optional[str]] = mapped_column(String(64), comment="目标表名")
    target_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment="目标记录主键ID")
    before_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="操作前快照")
    after_snapshot: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="操作后快照")
    request_ip: Mapped[str] = mapped_column(String(45), nullable=False, comment="请求IP地址")
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), comment="User-Agent")
    remark: Mapped[Optional[str]] = mapped_column(String(255), comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, comment="日志记录时间")

    def __repr__(self):
        return f"<AdminLog(id={self.id}, admin='{self.admin_phone}', action='{self.action_type}')>"