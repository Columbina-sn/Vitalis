import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn
from starlette.middleware.cors import CORSMiddleware

from tasks import run_daily_task_loop, run_cleanup_loop, run_backup_loop
from utills.exception_handlers import register_exception_handlers
from utills.logging_conf import setup_logging, get_logger  # 新增

from routers import auth, comment, user, chat, admin

# ---------- 初始化日志（必须在 FastAPI 之前） ----------
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task_summary = asyncio.create_task(run_daily_task_loop())
    task_cleanup = asyncio.create_task(run_cleanup_loop())
    task_backup = asyncio.create_task(run_backup_loop())
    logger.info("后台任务已启动：每日摘要 + 软删除清理 + 数据库备份")

    yield

    for t in (task_summary, task_cleanup, task_backup):
        t.cancel()
    try:
        await asyncio.gather(task_summary, task_cleanup, task_backup, return_exceptions=True)
    except Exception:
        pass
    logger.info("后台任务已全部取消")

app = FastAPI(title="Vitalis AI 后端", version="0.2.0", lifespan=lifespan)

app.mount("/HTML", StaticFiles(directory="HTML"), name="HTML")
app.mount("/static_pic", StaticFiles(directory="static_pic"), name="static_pic")
register_exception_handlers(app)

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
    uvicorn.run("main:app", port=8080, reload=True, log_config=None)