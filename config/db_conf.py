# config/db_conf
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from dotenv import load_dotenv

load_dotenv()

# 数据库连接字符串：mysql+aiomysql://用户名:密码@主机:端口/数据库名?charset=utf8mb4
ASYNC_DATABASE_URL = os.getenv("DATABASE_URL", "")
if not ASYNC_DATABASE_URL:
    raise EnvironmentError(
        "缺失 DATABASE_URL 环境变量，请配置数据库连接字符串。"
    )

# 创建异步数据库引擎实例
# 优化说明：
# - pool_size=5: 每个 worker 保持 5 个连接，4 个 worker 共 20 个常驻连接
# - max_overflow=10: 峰值时最多额外 10 个，避免连接数暴涨
# - pool_pre_ping=True: 检查连接是否存活，防止 MySQL 超时断开
# - pool_recycle=1800: 30 分钟回收连接，避免 MySQL wait_timeout 问题
# - pool_timeout=30: 获取连接最多等待 30 秒，避免无限阻塞
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_timeout=30
)

# 创建异步会话工厂，用于生成数据库会话对象
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_db():
    """获取数据库会话的依赖项，自动管理事务和异常回滚"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
