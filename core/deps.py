# core/deps.py
import os
from fastapi import Depends, HTTPException, status  # 导入 FastAPI 的依赖项工具 Depends，用于在路由中注入依赖
from fastapi.security import OAuth2PasswordBearer  # 导入 OAuth2 密码认证流程，用于从请求中提取 token
from jose import JWTError  # 导入 JWT 错误类型，用于捕获 token 解析过程中的异常
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # 导入 SQLAlchemy 异步会话，用于数据库操作

from config.db_conf import get_db  # 从配置模块导入获取数据库会话的函数
from crud.auth import is_admin_login_enabled
from crud.user import get_user_by_phone  # 从用户 CRUD 模块导入根据手机号查询用户的函数
from models import LoginHistory
from schemas.user import TokenData  # 从用户数据模型导入 TokenData 类，用于存放解析后的 token 数据
from utills.security import verify_token  # 从工具模块导入验证 JWT token 的函数
from utills.logging_conf import get_logger

logger = get_logger(__name__)


# 创建一个 OAuth2 密码认证流程实例，指定登录接口的 URL 为 "/auth/login"
# 当需要 token 时，FastAPI 会自动从请求头 Authorization 中提取 Bearer token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

ADMIN_PHONE = os.getenv("ADMIN_PHONE")


# 定义获取当前登录用户的依赖函数，它会被 FastAPI 自动调用
# 参数 token 通过 Depends(oauth2_scheme) 自动从请求中提取 token
# 参数 db 通过 Depends(get_db) 自动获取数据库会话
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    # 定义一个认证失败的异常，会在 token 无效或用户不存在时抛出
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,  # HTTP 状态码 401 表示未认证
        detail="无效的认证凭据",  # 错误详情
        headers={"WWW-Authenticate": "Bearer"},  # 告诉客户端应使用 Bearer 认证方式
    )
    try:
        # 调用工具函数 verify_token 验证 token 的有效性，并解析出 payload（数据部分）
        payload = verify_token(token)
        # 从 payload 中获取 "sub" 字段的值，按照 JWT 规范，"sub" 通常存放用户标识，这里存放手机号
        phone: str = payload.get("sub")
        # 如果手机号不存在，说明 payload 结构不对，抛出认证异常
        jti: str = payload.get("jti")
        # 检验jti
        if phone is None or jti is None:
            raise credentials_exception
        # 将手机号封装成 TokenData 对象，方便后续使用
        token_data = TokenData(phone=phone)
    except JWTError:
        # 如果解析过程中发生 JWT 相关错误（如 token 过期、签名错误等），也抛出认证异常
        raise credentials_exception

    # 根据手机号从数据库中查询对应的用户信息
    user = await get_user_by_phone(db, phone=token_data.phone)
    # 如果用户不存在，说明 token 中的手机号无效，抛出认证异常
    if user is None:
        raise credentials_exception
    # 如果用户不被允许登录，则禁止
    if not user.can_login:
        logger.warning(f"用户 {phone} 已被禁止登录")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账号已被禁止登录"
        )

    # --- 新增 JTI 一致性校验 ---
    if user.current_token_jti != jti:
        logger.warning(f"用户 {phone} 的 JTI 不匹配，可能在其他设备登录")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="会话已失效（已在其他设备登录）"
        )

    # --- 检查 login_history 有效性 ---
    login_history_stmt = select(LoginHistory).where(
        LoginHistory.token_jti == jti,
        LoginHistory.user_id == user.id,
        LoginHistory.is_valid == True
    )
    result = await db.execute(login_history_stmt)
    login_record = result.scalar_one_or_none()
    if login_record is None:
        logger.warning(f"用户 {phone} 的会话记录无效或已注销")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="会话已过期或已被注销"
        )

    # 返回用户对象，FastAPI 会将其注入到需要当前用户的路由参数中
    logger.debug(f"用户 {phone} 身份验证通过")
    return user


async def get_current_admin_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    管理员身份校验依赖，返回管理员基本信息字典。
    不依赖 users 表，管理员身份完全由环境变量和 token 中的 is_admin 字段决定。
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的管理员认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # 1. 验证 token 并获取 payload
    try:
        payload = verify_token(token)
    except Exception:
        logger.warning("管理员 token 验证失败")
        raise credentials_exception

    # 2. 检查 is_admin 字段
    if not payload.get("is_admin", False):
        logger.warning("非管理员尝试访问管理员接口")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限"
        )

    # 3. 检查手机号是否匹配环境变量中的管理员手机号
    phone = payload.get("sub")
    if phone != ADMIN_PHONE:
        logger.warning(f"管理员 token 中的手机号 {phone} 与配置不匹配")
        raise credentials_exception

    # 4. 检查熔断开关
    if not await is_admin_login_enabled(db):
        logger.warning("管理员登录入口已关闭，管理员请求被拒")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="管理员登录入口已关闭"
        )

    # 返回管理员信息字典，便于后续接口使用
    logger.debug(f"管理员 {phone} 身份验证通过")
    return {"phone": phone, "is_admin": True}