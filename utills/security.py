# utills/security.py
# 导入密码加密相关的库
import uuid
import warnings

from passlib.context import CryptContext

# 导入操作系统相关的模块，用于读取环境变量
import os
# 导入日期时间处理模块，用于设置 token 的过期时间
from datetime import datetime, timedelta, timezone
# 导入类型提示，让代码更容易理解（Optional 表示参数可以为空，Dict 表示字典类型）
from typing import Optional, Dict

# 从 jose 库中导入 jwt 模块，用于生成和验证 JSON Web Token（一种安全的 token 格式）
from jose import jwt
from jose.exceptions import JWTError
# 导入 dotenv 库，用于从 .env 文件加载环境变量（方便管理敏感信息）
from dotenv import load_dotenv


# 创建一个密码上下文对象，用于处理密码的哈希（加密）和验证
# schemes=["bcrypt"] 表示使用 bcrypt 这种加密算法
# deprecated="auto" 表示自动处理那些不再推荐的旧算法
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# 定义函数：将明文密码转换成哈希值（加密后的乱码）
def get_hash_password(password: str):
    # 调用密码上下文的 hash 方法对密码进行加密
    return pwd_context.hash(password)


# 定义函数：验证用户输入的明文密码和数据库中存储的哈希密码是否匹配
def verify_password(plain_password, hashed_password):
    # 调用密码上下文的 verify 方法，返回 True 或 False
    return pwd_context.verify(plain_password, hashed_password)


# 加载 .env 文件中的环境变量到当前运行环境中
load_dotenv()

# 从环境变量中获取秘钥，用于签名 JWT（必须保密，不能泄露）
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
if SECRET_KEY == "dev-secret-key-change-in-production":
    warnings.warn("⚠️ SECRET_KEY 使用默认开发密钥，请在生产环境中设置！")

# 从环境变量中获取加密算法，默认使用 HS256（一种常见的对称加密算法）
ALGORITHM = os.getenv("ALGORITHM", "HS512")

# 从环境变量中获取 token 的过期时间（分钟），默认设置为 1440 分钟
# int() 将字符串转换成整数
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))


# 定义函数：生成一个新的 JWT token
# data: 要放入 token 的信息（比如用户的手机号），必须是字典类型
# expires_delta: 可选参数，可以自定义过期时间，如果不传则使用默认的过期时间
# 新函数带有jti，旧函数只用于管理员token。话说搞来搞去居然管理员还没用户登录安全了吗……
def create_access_token(data: Dict[str, any], expires_delta: Optional[timedelta] = None) -> str:
    """
    生成 JWT token
    :param data: 要编码的数据（例如 {"sub": user.phone}）
    :param expires_delta: 过期时间，默认为环境变量中的 ACCESS_TOKEN_EXPIRE_MINUTES
    :return: JWT 字符串
    """
    # 复制传入的数据，避免直接修改原数据
    to_encode = data.copy()
    # 判断是否传入了自定义的过期时间
    if expires_delta:
        # 如果传入了，则用当前时间加上自定义的时长计算出过期时间点
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        # 如果没有传入，则用当前时间加上默认的分钟数计算出过期时间点
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # 将过期时间添加到要编码的数据中，JWT 规范中过期字段名称为 "exp"
    to_encode.update({"exp": expire})
    # 调用 jwt.encode 方法生成 token
    # 参数：要编码的数据，秘钥，算法
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    # 返回生成的 token 字符串
    return encoded_jwt


def create_access_token_with_jti(data: Dict[str, any], expires_delta: Optional[timedelta] = None) -> tuple[str, str]:
    """
    生成带唯一 jti 的 JWT，返回 (token, jti)
    """
    jti = uuid.uuid4().hex
    to_encode = data.copy()
    to_encode["jti"] = jti
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt, jti


# 定义函数：验证 token 的有效性，并返回 token 中包含的数据
def verify_token(token: str) -> Dict[str, any]:
    """
    验证 JWT token，返回 payload，如果无效则抛出异常
    """
    try:
        # 尝试解码 token，使用相同的秘钥和算法
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # 如果成功，返回解码后的数据（payload）
        return payload
    except JWTError:
        # 如果解码失败（比如 token 过期、被篡改、格式错误等），会抛出 JWTError 异常
        # 这里捕获异常后不做额外处理，直接重新抛出，让上层函数去处理（比如返回 401 错误）
        raise