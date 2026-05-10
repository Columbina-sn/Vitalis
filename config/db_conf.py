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
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,  # 数据库连接地址
    echo=False,  # 输出SQL语句日志，方便调试
    pool_size=10,  # 连接池中始终保持10个活跃连接
    max_overflow=20  # 当连接池不够用时，最多额外创建20个连接
)


# 创建异步会话工厂，用于生成数据库会话对象
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,  # 绑定到我们创建的数据库引擎
    class_=AsyncSession,  # 指定会话类为AsyncSession
    expire_on_commit=False  # 提交后不过期对象，避免重新查询数据库
)


async def get_db():  # 定义依赖项，用于获取数据库会话
    """获取数据库会话的依赖项，自动管理事务和异常回滚"""
    async with AsyncSessionLocal() as session:  # 创建异步会话
        try:
            yield session  # 将会话提供给路由处理函数
            await session.commit()  # 如果路由正常执行，则提交事务
        except Exception:  # 如果发生任何异常
            await session.rollback()  # 回滚事务
            raise  # 重新抛出异常，让FastAPI处理
        finally:
            await session.close()  # 最终确保会话被关闭