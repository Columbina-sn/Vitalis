# routers/chat.py
import asyncio
from datetime import date, datetime as dt
from typing import Optional
import difflib

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.deps import get_current_user
from crud.user import update_user_nickname, get_user_status_by_user_id
from models import User, RoleEnum
from schemas.chat import ChatRequest, ConversationHistoryResponse
from crud.chat import (
    get_user_full_info,
    update_user_status,
    add_emotion_shift,
    add_conversation_history,
    get_conversations_cursor_paginated,
    get_conversations_by_date,
    add_or_update_memory_anchor,
    create_schedule,
    check_recent_similar_schedule,
    check_recent_duplicate_emotion_shift,
    update_schedule,
    delete_schedule, auto_complete_due_schedules,
)
from ai.empathyAI import build_messages as empathy_build_messages, analog_ai as empathy_analog_ai
from ai.productivityAI import build_messages as productivity_build_messages, analog_ai as productivity_analog_ai
from config.db_conf import get_db
from utills.response import success_response
from utills.logging_conf import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["聊天"])


def debug_print(obj):
    """调试打印：将对象中的字面 \n 转换为实际换行"""
    text = str(obj).replace('\\n', '\n')
    logger.debug(text)


@router.post("/conversation", summary="接受、处理、回复用户消息")
async def receive_user_message(
        req: ChatRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    # 1. 获取完整用户信息
    user_info = await get_user_full_info(db, current_user.id)
    if user_info is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 2. 自动完成到期日程
    await auto_complete_due_schedules(db, current_user.id)

    # 3. 准备日程映射
    upcoming = user_info.get("upcoming_schedules", [])
    schedule_map = {}
    for sch in upcoming:
        schedule_map.setdefault(sch.title, []).append(sch)

    # 4. 并行调用情感 AI 与工作 AI
    empathy_msgs = empathy_build_messages(req.message, user_info)
    prod_msgs = productivity_build_messages(req.message, user_info)
    debug_print(empathy_msgs)
    debug_print(prod_msgs)

    empathy_task = empathy_analog_ai(empathy_msgs)
    prod_task = productivity_analog_ai(prod_msgs)

    empathy_result, prod_result = await asyncio.gather(empathy_task, prod_task)
    debug_print(empathy_result)
    debug_print(prod_result)

    empathy_reply = empathy_result["reply"]

    # 5. 记录用户消息
    await add_conversation_history(db, current_user.id, RoleEnum.user, req.message)

    # 6. 更新五维状态
    status_changes = prod_result.get("status_changes", {})
    if status_changes:
        await update_user_status(db, current_user.id, status_changes)
        updated_status = await get_user_status_by_user_id(db, current_user.id)
        if updated_status:
            status_changes["psychological_harmony_index"] = updated_status.psychological_harmony_index

    # 7. 记录情绪转折
    if prod_result.get("should_add_emotion_shifts") and prod_result["emotion_shifts_summary"]:
        detail = prod_result["emotion_shifts_summary"]
        if not await check_recent_duplicate_emotion_shift(db, current_user.id, detail):
            await add_emotion_shift(db, current_user.id, emotion_change_detail=detail)

    # 8. 更新用户画像
    if prod_result.get("should_update_anchors") and prod_result["new_anchors"]:
        for anchor_data in prod_result["new_anchors"]:
            if isinstance(anchor_data, str):
                anchor_data = {"content": anchor_data, "anchor_type": "note", "confidence": 0.5}
            await add_or_update_memory_anchor(
                db, current_user.id,
                anchor_type=anchor_data.get("anchor_type", "note"),
                content=anchor_data.get("content", ""),
                confidence=anchor_data.get("confidence", 0.5),
            )

    # 9. 创建新日程
    if prod_result.get("should_create_schedule") and prod_result.get("new_schedules"):
        for sched in prod_result["new_schedules"]:
            if not sched.get("title"):
                continue
            if not await check_recent_similar_schedule(
                db, current_user.id,
                sched.get("schedule_type", ""),
                sched.get("title", "")
            ):
                raw_time = sched.get("scheduled_time")
                scheduled_time = None
                if raw_time and isinstance(raw_time, str):
                    try:
                        scheduled_time = dt.fromisoformat(raw_time)
                    except ValueError:
                        pass
                await create_schedule(
                    db, current_user.id,
                    schedule_type=sched.get("schedule_type", "short_task"),
                    title=sched.get("title", ""),
                    description=sched.get("description"),
                    scheduled_time=scheduled_time,
                )

    # 10. 编辑日程（精确+模糊匹配，静默处理）
    if prod_result.get("schedule_edits"):
        for edit in prod_result["schedule_edits"]:
            old_title = edit.get("title", "")
            if not old_title:
                continue
            target = None
            if old_title in schedule_map:
                target = schedule_map[old_title][0]
            else:
                best_ratio, best_sch = 0.0, None
                for sch in upcoming:
                    ratio = difflib.SequenceMatcher(None, old_title, sch.title).ratio()
                    if ratio > best_ratio:
                        best_ratio, best_sch = ratio, sch
                if best_ratio >= 0.7:
                    target = best_sch
            if target:
                updates = {}
                if "new_title" in edit and edit["new_title"]:
                    updates["title"] = edit["new_title"]
                if "new_description" in edit:
                    updates["description"] = edit["new_description"]
                if "new_scheduled_time" in edit:
                    try:
                        updates["scheduled_time"] = dt.fromisoformat(edit["new_scheduled_time"])
                    except ValueError:
                        pass
                if "new_type" in edit and edit["new_type"]:
                    updates["schedule_type"] = edit["new_type"]
                if "new_completed" in edit and edit["new_completed"] is not None:
                    updates["is_completed"] = edit["new_completed"]
                if updates:
                    await update_schedule(db, target.id, updates)

    # 11. 删除日程（静默处理）
    if prod_result.get("schedule_deletes"):
        for del_item in prod_result["schedule_deletes"]:
            title_to_del = del_item.get("title", "")
            if not title_to_del:
                continue
            target = None
            if title_to_del in schedule_map:
                target = schedule_map[title_to_del][0]
            else:
                best_ratio, best_sch = 0.0, None
                for sch in upcoming:
                    ratio = difflib.SequenceMatcher(None, title_to_del, sch.title).ratio()
                    if ratio > best_ratio:
                        best_ratio, best_sch = ratio, sch
                if best_ratio >= 0.7:
                    target = best_sch
            if target:
                await delete_schedule(db, target.id)

    # 12. 改名
    update_nickname = prod_result.get("update_nickname")
    if update_nickname:
        await update_user_nickname(db, current_user.id, update_nickname)

    # 13. 最终回复完全使用情感 AI 的原始输出
    final_reply = empathy_reply

    # 14. 记录ai回复
    await add_conversation_history(
        db, current_user.id, RoleEnum.assistant,
        final_reply,
        extra_metadata=prod_result  # 将工作 AI 的完整 JSON 作为元数据存入
    )
    await db.commit()

    logger.info(f"用户 {current_user.id} 对话处理完成")
    return success_response(message="回复用户成功", data={
        "reply": final_reply,
        "status_updates": status_changes,
    })


@router.get("/history", summary="游标分页获取对话历史记录")
async def get_chat_history(
        before_id: Optional[int] = Query(None, description="游标：上一页最后一条消息的ID，不传则获取最新"),
        page_size: int = Query(20, ge=1, le=50, alias="pageSize", description="每页条数"),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    records, has_more = await get_conversations_cursor_paginated(
        db, current_user.id, before_id=before_id, limit=page_size
    )
    return success_response(message="获取对话记录成功", data={
        "list": [ConversationHistoryResponse.model_validate(rec) for rec in records],
        "hasMore": has_more
    })


@router.get("/history/date", summary="获取指定日期的对话历史")
async def get_chat_history_by_date(
        target_date: date = Query(..., alias="date", description="查询日期 YYYY-MM-DD"),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    records = await get_conversations_by_date(db, current_user.id, target_date)
    return success_response(message="获取指定日期对话记录成功", data={
        "list": [ConversationHistoryResponse.model_validate(rec) for rec in records],
        "total": len(records)
    })