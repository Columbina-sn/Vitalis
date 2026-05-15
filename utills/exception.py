# utills/exception.py
import traceback  # 导入traceback模块，用于格式化异常信息，方便调试

from fastapi import HTTPException, Request  # 导入FastAPI的HTTPException异常类和Request请求类
from fastapi.exceptions import RequestValidationError  # 导入FastAPI的请求验证错误类
from fastapi.responses import JSONResponse  # 导入JSONResponse，用于返回JSON格式的响应
from sqlalchemy.exc import IntegrityError, SQLAlchemyError  # 导入SQLAlchemy的完整性错误和通用数据库错误
from starlette import status  # 导入status，包含HTTP状态码常量

# import json
from typing import Any

# 开发模式：返回详细错误信息
# 生产模式：返回简化错误信息
DEBUG_MODE = False  # 教学项目保持开启，上线后应关闭。True表示开发模式，会返回详细的错误信息；False表示生产模式，只返回简化的错误信息


async def http_exception_handler(request: Request, exc: HTTPException):
    """
    处理 HTTPException 异常
    """
    # HTTPException 通常是业务逻辑主动抛出的，data 保持 None
    return JSONResponse(
        status_code=exc.status_code,  # 使用异常中携带的HTTP状态码
        content={
            "code": exc.status_code,  # 响应中的code字段，与状态码一致
            "message": exc.detail,  # 响应中的message字段，从异常中获取详细信息
            "data": None  # 响应中的data字段，这里设置为None，不返回额外数据
        }
    )


async def integrity_error_handler(request: Request, exc: IntegrityError):
    """
    处理数据库完整性约束错误（例如唯一键冲突、外键约束失败等）
    """
    error_msg = str(exc.orig)  # 获取原始数据库错误信息（字符串形式）

    # 判断具体的约束错误类型，并生成用户友好的提示信息
    if "username_UNIQUE" in error_msg or "Duplicate entry" in error_msg:
        detail = "用户名已存在"  # 如果是用户名重复的错误
    elif "FOREIGN KEY" in error_msg:
        detail = "关联数据不存在"  # 如果是外键约束失败
    else:
        detail = "数据约束冲突，请检查输入"  # 其他约束错误

    # 开发模式下返回详细错误信息（用于调试）
    error_data = None
    if DEBUG_MODE:
        error_data = {
            "error_type": "IntegrityError",  # 错误类型
            "error_detail": error_msg,  # 原始错误信息
            "path": str(request.url)  # 请求的URL路径
        }

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,  # 返回400状态码（客户端错误）
        content={
            "code": 400,  # 响应code为400
            "message": detail,  # 用户友好的错误信息
            "data": error_data  # 可能包含的调试数据（开发模式下有，生产模式下为None）
        }
    )


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    """
    处理 SQLAlchemy 数据库错误（除完整性错误外的其他数据库错误）
    """
    # 开发模式下返回详细错误信息（用于调试）
    error_data = None
    if DEBUG_MODE:
        error_data = {
            "error_type": type(exc).__name__,  # 异常的类型名称
            "error_detail": str(exc),  # 异常详细信息
            "traceback": traceback.format_exc(),  # 异常的堆栈跟踪信息（方便定位问题）
            "path": str(request.url)  # 请求的URL路径
        }

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,  # 返回500状态码（服务器内部错误）
        content={
            "code": 500,  # 响应code为500
            "message": "数据库操作失败，请稍后重试",  # 通用错误提示，不暴露具体技术细节
            "data": error_data  # 可能包含的调试数据
        }
    )


# utills/exception.py 中替换原 validation_exception_handler 为以下内容


def make_json_serializable(obj: Any) -> Any:
    """递归地将对象转换为 JSON 可序列化的类型"""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    if isinstance(obj, Exception):
        # 将异常对象转为字符串
        return str(obj)
    if isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [make_json_serializable(item) for item in obj]
    # 其他无法转换的类型，转为字符串
    return str(obj)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    处理请求参数验证错误（例如Pydantic模型验证失败）
    """
    # 深拷贝错误列表并确保所有内容可 JSON 序列化
    errors = make_json_serializable(exc.errors())
    return JSONResponse(
        status_code=422,
        content={
            "code": 422,
            "message": "请求参数验证失败",
            "data": errors if DEBUG_MODE else None
        }
    )


async def general_exception_handler(request: Request, exc: Exception):
    """
    处理所有未捕获的异常（兜底处理器）
    """
    # 开发模式下返回详细错误信息（用于调试）
    error_data = None
    if DEBUG_MODE:
        error_data = {
            "error_type": type(exc).__name__,  # 异常类型
            "error_detail": str(exc),  # 异常信息
            "traceback": traceback.format_exc(),  # 堆栈跟踪
            "path": str(request.url)  # 请求URL
        }

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,  # 返回500状态码
        content={
            "code": 500,  # 响应code为500
            "message": "服务器内部错误",  # 通用错误提示
            "data": error_data  # 可能包含的调试数据
        }
    )