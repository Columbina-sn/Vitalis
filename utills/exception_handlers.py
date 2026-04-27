# utills/exception_handlers.py
from fastapi import HTTPException  # 导入 FastAPI 内置的 HTTP 异常类，用于处理 HTTP 请求过程中出现的业务错误（如 404、400 等）
from fastapi.exceptions import RequestValidationError  # 导入请求数据验证失败的异常类，当客户端发送的数据不符合接口要求时会触发
from sqlalchemy.exc import IntegrityError, SQLAlchemyError  # 导入 SQLAlchemy 的数据库异常：IntegrityError
# 是数据完整性错误（如唯一键冲突），SQLAlchemyError 是所有数据库操作异常的基类

# 从自定义的工具包（utills.exception）中导入各个异常处理函数，这些函数定义了当特定异常发生时应该返回怎样的响应给客户端
from utills.exception import (http_exception_handler,
                              integrity_error_handler,
                              sqlalchemy_error_handler,
                              general_exception_handler,
                              validation_exception_handler)


def register_exception_handlers(app):
    """
    注册全局异常处理 子类在前 父类在后 具体在前 抽象在后
    这个函数的作用是将不同类型的异常与对应的处理函数绑定到 FastAPI 应用上，
    这样当异常发生时，FastAPI 就会自动调用我们指定的函数来处理它。
    """
    # 将 HTTPException 异常绑定到 http_exception_handler 处理函数
    # 这通常用于处理开发者主动抛出的业务异常（比如用户不存在、权限不足等）
    app.add_exception_handler(HTTPException, http_exception_handler)  # 业务

    # 将数据库完整性错误（IntegrityError）绑定到 integrity_error_handler
    # 比如插入重复数据违反唯一约束时，就会进入这个处理流程
    app.add_exception_handler(IntegrityError, integrity_error_handler)  # 数据完整性约束

    # 将通用的 SQLAlchemy 数据库异常绑定到 sqlalchemy_error_handler
    # 如果发生其他数据库相关错误（如连接失败、语法错误等），会被这里捕获
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_error_handler)  # 数据库错误

    # 将请求数据验证失败异常绑定到 validation_exception_handler
    # 当客户端传来的参数类型不对、缺少必填字段时，由它来返回清晰的错误提示
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # 将最顶级的 Exception 异常绑定到 general_exception_handler
    # 这是“兜底”处理，用来捕获所有未被上面特定处理器处理的异常，防止程序崩溃并返回一个友好的错误信息
    app.add_exception_handler(Exception, general_exception_handler)  # 兜底