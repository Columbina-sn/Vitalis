import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
from starlette.middleware.cors import CORSMiddleware

from utills.exception_handlers import register_exception_handlers

from routers import auth, comment, user, chat, admin

app = FastAPI(title="Vitalis AI 后端接口文档", version="0.1.0")

app.mount("/HTML", StaticFiles(directory="HTML"), name="HTML")
app.mount("/static_pic", StaticFiles(directory="static_pic"), name="static_pic")

register_exception_handlers(app)

# 从环境变量读取允许的来源列表，若未配置则使用默认的本地开发地址
# 目前.env没写 将来记得写
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(auth.router)
app.include_router(comment.router)
app.include_router(user.router)
app.include_router(chat.router)
app.include_router(admin.router)


@app.get("/", summary="进入首页（登录页）")
async def read_index():
    with open("HTML/Index/index.html", "r", encoding="utf-8") as f:
        content = f.read()
    return HTMLResponse(content)

if __name__ == "__main__":
    uvicorn.run("main:app", port=8080, reload=True)