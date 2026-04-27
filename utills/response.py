# utills/response.py
# 从 FastAPI 框架中导入 JSONResponse 类，用于返回 JSON 格式的 HTTP 响应
from fastapi.responses import JSONResponse

# 从 FastAPI 框架中导入 jsonable_encoder 函数，用于将 Python 对象（如自定义类、日期等）转换成 JSON 兼容的数据类型
from fastapi.encoders import jsonable_encoder


# 定义一个名为 success_response 的函数，用于生成统一的“成功”响应格式
# 参数 message 是响应中的提示信息，默认值为 "success"
# 参数 data 是要返回的数据，可以是任意 Python 对象（列表、字典、自定义对象等），默认值为 None
def success_response(message: str = "success", data=None):
    # 构建一个字典，包含三个固定的字段：
    # - code: HTTP 状态码（这里固定为 200，表示成功）
    # - message: 从函数参数传入的提示信息
    # - data: 从函数参数传入的实际数据
    content = {
        "code": 200,
        "message": message,
        "data": data
    }
    # 下面这行注释的意思是：确保无论 data 里面是什么类型的对象，都能被正确转换成 JSON 格式返回。
    # 具体做法是：先用 jsonable_encoder 将 content 字典里的所有值转换成 JSON 兼容的类型，
    # 然后交给 JSONResponse 生成一个标准的 HTTP 响应返回给客户端。
    return JSONResponse(content=jsonable_encoder(content))