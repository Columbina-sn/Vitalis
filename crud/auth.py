from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models import SystemConfig


async def is_admin_login_enabled(db: AsyncSession) -> bool:
    """读取 system_config 表中 admin_login_enabled 配置项"""
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.config_key == "admin_login_enabled")
    )
    config = result.scalar_one_or_none()
    if config is None:
        return False  # 默认关闭
    return config.config_value.lower() == "true"