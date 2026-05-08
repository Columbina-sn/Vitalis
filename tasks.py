# tasks.py
import os

from dotenv import load_dotenv
load_dotenv()

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from ai.summaryAI import generate_daily_summary
from config.db_conf import AsyncSessionLocal
from crud.admin import create_admin_log
from models import ConversationHistory, MemorySnapshot, User, Comment


async def daily_summary_task(
    admin_phone="system",
    action_type="DAILY_SUMMARY",
    request_ip="127.0.0.1",
    user_agent="CronJob",
    remark_prefix="定时任务自动触发"
):
    """
    定时任务：每天凌晨4点运行，为所有当天有对话记录的用户生成记忆快照。
    """
    async with AsyncSessionLocal() as db:
        # 查询今天有对话记录的用户ID（去重）
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        stmt = (
            select(ConversationHistory.user_id)
            .where(
                ConversationHistory.created_at >= today_start,
                ConversationHistory.created_at < today_end
            )
            .distinct()
        )
        result = await db.execute(stmt)
        user_ids = result.scalars().all()

        for uid in user_ids:
            # 获取该用户今天所有对话，按时间正序
            conv_stmt = (
                select(ConversationHistory)
                .where(
                    ConversationHistory.user_id == uid,
                    ConversationHistory.created_at >= today_start,
                    ConversationHistory.created_at < today_end
                )
                .order_by(ConversationHistory.created_at.asc())
            )
            convs = (await db.execute(conv_stmt)).scalars().all()

            if not convs:
                continue

            # 构造文本数组
            conv_texts = []
            for c in convs:
                role_str = "小元" if c.role.value == "assistant" else "用户"
                conv_texts.append(f"[{role_str}] {c.content}")

            # 获取用户昵称（如果存在）
            user = await db.get(User, uid)
            nickname = user.nickname if user and user.nickname else "用户"

            summary_text = await generate_daily_summary(conv_texts, nickname)

            snapshot = MemorySnapshot(
                user_id=uid,
                summary=summary_text,
                created_at=datetime.now()
            )
            db.add(snapshot)

        # 记录管理员日志
        await create_admin_log(
            db=db,
            admin_phone=admin_phone,
            action_type=action_type,
            request_ip=request_ip,
            user_agent=user_agent,
            remark=f"{remark_prefix}，生成记忆快照，涉及 {len(user_ids)} 位用户"
        )
        await db.commit()


TZ = timezone(timedelta(hours=8))


async def run_daily_task_loop():
    while True:
        now = datetime.now(TZ)  # 带时区的当前时间
        next_run = now.replace(hour=4, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        wait_seconds = (next_run - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        await daily_summary_task()


AVATAR_UPLOAD_DIR = os.getenv("AVATAR_UPLOAD_DIR", "static_pic/avatar")
DEFAULT_AVATAR_URL = os.getenv("DEFAULT_AVATAR_URL", "/static_pic/default_avatar.jpg")


async def cleanup_soft_deleted_records():
    """每天凌晨3点运行，物理删除冷却期到期的用户和评论"""
    async with AsyncSessionLocal() as db:
        try:
            now = datetime.now()

            # 清理用户（注销后保留30天）
            expire_user_date = now - timedelta(days=30)
            stmt = select(User).where(
                User.is_deleted == True,
                User.deleted_at <= expire_user_date
            )
            result = await db.execute(stmt)
            expired_users = result.scalars().all()

            for user in expired_users:
                # 清理头像文件
                try:
                    if user.avatar and user.avatar != DEFAULT_AVATAR_URL:
                        avatar_relative = user.avatar.lstrip("/")
                        filename = os.path.basename(avatar_relative)
                        file_path = os.path.join(AVATAR_UPLOAD_DIR, filename)
                        if os.path.abspath(file_path).startswith(os.path.abspath(AVATAR_UPLOAD_DIR)):
                            if os.path.exists(file_path) and os.path.isfile(file_path):
                                os.remove(file_path)
                except Exception as e:
                    print(f"清理用户头像失败 user_id={user.id}: {e}")
                # 物理删除用户（级联删除所有关联数据）
                await db.delete(user)

            # 清理评论（软删除后保留90天）
            expire_comment_date = now - timedelta(days=90)
            stmt = select(Comment).where(
                Comment.is_deleted == True,
                Comment.deleted_at <= expire_comment_date
            )
            result = await db.execute(stmt)
            expired_comments = result.scalars().all()
            for comment in expired_comments:
                await db.delete(comment)

            await db.commit()

            # 记录管理员日志
            if expired_users or expired_comments:
                await create_admin_log(
                    db=db,
                    admin_phone="system",
                    action_type="AUTO_CLEANUP",
                    request_ip="127.0.0.1",
                    remark=f"自动清理：删除{len(expired_users)}个用户、{len(expired_comments)}条评论"
                )
                await db.commit()
                print(f"[定时清理] 已清理 {len(expired_users)} 用户, {len(expired_comments)} 评论")
        except Exception as e:
            await db.rollback()
            print(f"定时清理任务失败: {e}")


async def run_cleanup_loop():
    """每天凌晨3点执行一次清理"""
    while True:
        now = datetime.now(TZ)
        next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
        if now >= next_run:
            next_run += timedelta(days=1)
        wait_seconds = (next_run - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        await cleanup_soft_deleted_records()