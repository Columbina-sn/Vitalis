# crud/auth.py
from sqlalchemy import select
from sqlalchemy import update as sql_update
from sqlalchemy.ext.asyncio import AsyncSession
from models import SystemConfig, LoginHistory


async def is_admin_login_enabled(db: AsyncSession) -> bool:
    """读取 system_config 表中 admin_login_enabled 配置项"""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == "admin_login_enabled")
    )
    config = result.scalar_one_or_none()
    if config is None:
        return False  # 默认关闭
    return config.config_value.lower() == "true"


async def invalidate_previous_sessions(db: AsyncSession, user_id: int):
    """将指定用户所有有效会话标记为无效"""
    await db.execute(
        sql_update(LoginHistory)
        .where(LoginHistory.user_id == user_id, LoginHistory.is_valid == True)
        .values(is_valid=False)
    )


async def create_login_history(db: AsyncSession, user_id: int, ip: str, location: str, device_info: str, jti: str) -> LoginHistory:
    """创建一条登录历史记录，并立即 flush 以获取 id"""
    record = LoginHistory(
        user_id=user_id,
        login_ip=ip,
        location=location,
        device_info=device_info,
        token_jti=jti,
        is_valid=True
    )
    db.add(record)
    await db.flush()   # 确保 id 被赋值，供后续查询使用
    return record