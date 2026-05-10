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

# ---------- 新增日志模块 ----------
from utills.logging_conf import get_logger
logger = get_logger(__name__)

TZ = timezone(timedelta(hours=8))


async def daily_summary_task(
    admin_phone="system",
    action_type="DAILY_SUMMARY",
    request_ip="127.0.0.1",
    user_agent="CronJob",
    remark_prefix="定时任务自动触发"
):
    """
    定时任务 / 管理员手动触发的每日总结生成。
    触发时间规则：
        - 凌晨 0:00 ~ 4:59  → 统计「昨天」全天数据（00:00:00 ~ 24:00:00）
        - 其他时间（5:00~23:59）→ 统计「今天」从 00:00:00 到当前时刻的数据
    """
    async with AsyncSessionLocal() as db:
        now = datetime.now(TZ)
        hour = now.hour

        if hour < 5:
            target_date = now.date() - timedelta(days=1)
            start_time = datetime.combine(target_date, datetime.min.time(), tzinfo=TZ)
            end_time = start_time + timedelta(days=1)
            date_desc = target_date.isoformat()
        else:
            target_date = now.date()
            start_time = datetime.combine(target_date, datetime.min.time(), tzinfo=TZ)
            end_time = now
            date_desc = target_date.isoformat()

        stmt = (
            select(ConversationHistory.user_id)
            .where(
                ConversationHistory.created_at >= start_time,
                ConversationHistory.created_at < end_time
            )
            .distinct()
        )
        result = await db.execute(stmt)
        user_ids = result.scalars().all()

        for uid in user_ids:
            conv_stmt = (
                select(ConversationHistory)
                .where(
                    ConversationHistory.user_id == uid,
                    ConversationHistory.created_at >= start_time,
                    ConversationHistory.created_at < end_time
                )
                .order_by(ConversationHistory.created_at.asc())
            )
            convs = (await db.execute(conv_stmt)).scalars().all()
            if not convs:
                continue

            conv_texts = []
            for c in convs:
                role_str = "小元" if c.role.value == "assistant" else "用户"
                conv_texts.append(f"[{role_str}] {c.content}")

            user = await db.get(User, uid)
            nickname = user.nickname if user and user.nickname else "用户"

            summary_text = await generate_daily_summary(conv_texts, nickname)

            snapshot = MemorySnapshot(
                user_id=uid,
                summary=summary_text,
                created_at=now
            )
            db.add(snapshot)

        remark = f"{remark_prefix}，统计日期 {date_desc}，涉及 {len(user_ids)} 位用户"
        await create_admin_log(
            db=db,
            admin_phone=admin_phone,
            action_type=action_type,
            request_ip=request_ip,
            user_agent=user_agent,
            remark=remark
        )
        await db.commit()
        logger.info(f"已完成每日摘要生成：{remark}")  # 信息替换


async def run_daily_task_loop():
    while True:
        try:
            now = datetime.now(TZ)
            next_run = now.replace(hour=4, minute=0, second=0, microsecond=0)
            if now >= next_run:
                next_run += timedelta(days=1)
            wait_seconds = (next_run - now).total_seconds()
            await asyncio.sleep(wait_seconds)
            await daily_summary_task()
        except Exception as e:
            logger.error("每日总结任务异常", exc_info=True)
            await asyncio.sleep(60)


AVATAR_UPLOAD_DIR = os.getenv("AVATAR_UPLOAD_DIR", "static_pic/avatar")
DEFAULT_AVATAR_URL = os.getenv("DEFAULT_AVATAR_URL", "/static_pic/default_avatar.jpg")


async def cleanup_soft_deleted_records(
    admin_phone="system",
    action_type="AUTO_CLEANUP",
    request_ip="127.0.0.1",
    remark_prefix="定时任务自动触发"
):
    """每天凌晨3点运行，物理删除冷却期到期的用户和评论"""
    async with AsyncSessionLocal() as db:
        try:
            now = datetime.now(TZ)

            expire_user_date = now - timedelta(days=30)
            stmt = select(User).where(
                User.is_deleted == True,
                User.deleted_at <= expire_user_date
            )
            result = await db.execute(stmt)
            expired_users = result.scalars().all()

            for user in expired_users:
                try:
                    if user.avatar and user.avatar != DEFAULT_AVATAR_URL:
                        avatar_relative = user.avatar.lstrip("/")
                        filename = os.path.basename(avatar_relative)
                        file_path = os.path.join(AVATAR_UPLOAD_DIR, filename)
                        if os.path.abspath(file_path).startswith(os.path.abspath(AVATAR_UPLOAD_DIR)):
                            if os.path.exists(file_path) and os.path.isfile(file_path):
                                os.remove(file_path)
                except Exception as e:
                    logger.error(f"清理用户头像失败 user_id={user.id}", exc_info=True)

                await db.delete(user)

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

            if expired_users or expired_comments:
                await create_admin_log(
                    db=db,
                    admin_phone=admin_phone,
                    action_type=action_type,
                    request_ip=request_ip,
                    remark=f"{remark_prefix}，删除{len(expired_users)}个用户、{len(expired_comments)}条评论"
                )
                await db.commit()
                logger.info(f"已清理 {len(expired_users)} 用户, {len(expired_comments)} 评论")  # 信息替换
        except Exception as e:
            await db.rollback()
            logger.error("定时清理任务失败", exc_info=True)


async def run_cleanup_loop():
    while True:
        try:
            now = datetime.now(TZ)
            next_run = now.replace(hour=3, minute=0, second=0, microsecond=0)
            if now >= next_run:
                next_run += timedelta(days=1)
            wait_seconds = (next_run - now).total_seconds()
            await asyncio.sleep(wait_seconds)
            await cleanup_soft_deleted_records()
        except Exception as e:
            logger.error("定时清理任务异常", exc_info=True)
            await asyncio.sleep(60)


async def backup_database_task(
    admin_phone="system",
    action_type="AUTO_BACKUP",
    request_ip="127.0.0.1",
    user_agent="CronJob",
    remark_prefix="定时任务自动触发"
):
    """执行备份，并（可选）记录操作日志。"""
    loop = asyncio.get_running_loop()
    from utills.backup import perform_backup
    await loop.run_in_executor(None, perform_backup)

    try:
        async with AsyncSessionLocal() as db:
            await create_admin_log(
                db=db,
                admin_phone=admin_phone,
                action_type=action_type,
                request_ip=request_ip,
                user_agent=user_agent,
                remark=f"{remark_prefix}，执行数据库备份"
            )
            await db.commit()
    except Exception as e:
        logger.error("备份日志记录失败", exc_info=True)


async def run_backup_loop():
    while True:
        try:
            now = datetime.now(TZ)
            next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
            if now >= next_run:
                next_run += timedelta(days=1)
            wait_seconds = (next_run - now).total_seconds()
            logger.info(f"下次备份时间: {next_run}")  # 信息替换
            await asyncio.sleep(wait_seconds)

            logger.info("开始执行备份...")
            await backup_database_task()
            logger.info("备份完成。")
        except Exception as e:
            logger.error("备份循环异常", exc_info=True)
            await asyncio.sleep(60)