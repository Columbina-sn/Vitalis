# routers/chat.py
import asyncio
from datetime import date, datetime as dt
from typing import Optional
import difflib  # 模糊匹配

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
    delete_schedule,
)
from ai.empathyAI import build_messages as empathy_build_messages, analog_ai as empathy_analog_ai
from ai.productivityAI import build_messages as productivity_build_messages, analog_ai as productivity_analog_ai
from config.db_conf import get_db
from utills.response import success_response

router = APIRouter(prefix="/chat", tags=["聊天"])


@router.post("/conversation", summary="接受、处理、回复用户消息")
async def receive_user_message(
        req: ChatRequest,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    # 1. 获取用户全局信息
    user_info = await get_user_full_info(db, current_user.id)
    if user_info is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 2. 获取未完成日程，构建匹配映射表
    upcoming_schedules = user_info.get("upcoming_schedules", [])
    schedule_map = {}
    for sch in upcoming_schedules:
        schedule_map.setdefault(sch.title, []).append(sch)

    # 3. 并行调用情感 AI 与工作 AI
    empathy_messages = empathy_build_messages(req.message, user_info)
    productivity_messages = productivity_build_messages(
        user_message=req.message,
        user_info=user_info,
    )

    empathy_task = empathy_analog_ai(empathy_messages)
    prod_task = productivity_analog_ai(productivity_messages)

    empathy_result, prod_result = await asyncio.gather(empathy_task, prod_task)

    empathy_reply = empathy_result["reply"]
    await add_conversation_history(db, current_user.id, RoleEnum.user, req.message)

    # 4. 更新五维状态
    status_changes = prod_result.get("status_changes", {})
    if status_changes:
        await update_user_status(db, current_user.id, status_changes)
        updated_status = await get_user_status_by_user_id(db, current_user.id)
        if updated_status:
            status_changes["psychological_harmony_index"] = updated_status.psychological_harmony_index

    # 5. 记录情绪转折（防重复）
    if prod_result.get("should_add_emotion_shifts") and prod_result["emotion_shifts_summary"]:
        if not await check_recent_duplicate_emotion_shift(db, current_user.id, prod_result["emotion_shifts_summary"]):
            await add_emotion_shift(db, current_user.id,
                                    emotion_change_detail=prod_result["emotion_shifts_summary"])

    # 6. 更新用户画像
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

    # 7. 创建新日程（批量）
    if prod_result.get("should_create_schedule") and prod_result.get("new_schedules"):
        for sched in prod_result["new_schedules"]:
            if not sched.get("title"):
                continue
            if not await check_recent_similar_schedule(db, current_user.id, sched.get("schedule_type", ""), sched.get("title", "")):
                raw_time = sched.get("scheduled_time")
                scheduled_time = None
                if raw_time and isinstance(raw_time, str):
                    try:
                        scheduled_time = dt.fromisoformat(raw_time)
                    except ValueError:
                        pass
                await create_schedule(db, current_user.id,
                                      schedule_type=sched.get("schedule_type", "short_task"),
                                      title=sched.get("title", ""),
                                      description=sched.get("description"),
                                      scheduled_time=scheduled_time)

    # 8. 编辑日程（精确匹配 + 模糊匹配）
    unmatched_edits = []
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
                for sch in upcoming_schedules:
                    ratio = difflib.SequenceMatcher(None, old_title, sch.title).ratio()
                    if ratio > best_ratio:
                        best_ratio, best_sch = ratio, sch
                if best_ratio >= 0.7:
                    target = best_sch
                else:
                    unmatched_edits.append(old_title)
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

    # 9. 删除日程
    unmatched_deletes = []
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
                for sch in upcoming_schedules:
                    ratio = difflib.SequenceMatcher(None, title_to_del, sch.title).ratio()
                    if ratio > best_ratio:
                        best_ratio, best_sch = ratio, sch
                if best_ratio >= 0.7:
                    target = best_sch
                else:
                    unmatched_deletes.append(title_to_del)
            if target:
                await delete_schedule(db, target.id)

    # 10. 拼装最终回复（温和版追问）
    final_reply = empathy_reply
    follow_up = prod_result.get("follow_up_text", "").strip()

    inquiry_parts = []
    if unmatched_edits:
        titles_edit = "“" + "”、“".join(unmatched_edits) + "”"
        if len(unmatched_edits) == 1:
            edit_clause = f"刚才你想编辑的那个日程（{titles_edit}），我在你的列表里没找到完全一样名字的"
        else:
            edit_clause = f"你提到的那几个日程（{titles_edit}），我没能在你已有的日程里对上号"
        inquiry_parts.append(edit_clause + "，能稍微再给我一点提示吗？比如大概是什么时候加的、或者里面写了什么字～")

    if unmatched_deletes:
        titles_delete = "“" + "”、“".join(unmatched_deletes) + "”"
        if len(unmatched_deletes) == 1:
            del_clause = f"你说想删除的那个日程（{titles_delete}），我试着找了但没定位到它"
        else:
            del_clause = f"你提到的几个想要删除的日程（{titles_delete}），我没能在你的日程里找到"
        inquiry_parts.append(del_clause + "，可以告诉我它们大概的名字或者内容吗？我再帮你核对一下～")

    if inquiry_parts:
        follow_up = (follow_up + "\n\n" + "🌱 另外，" + "；".join(inquiry_parts)).strip()

    if follow_up:
        final_reply = final_reply.rstrip() + "\n\n" + follow_up

    # 11. 处理改名
    update_nickname = prod_result.get("update_nickname")
    if update_nickname:
        await update_user_nickname(db, current_user.id, update_nickname)
        if not follow_up or "记住" not in follow_up:
            final_reply += f"\n好的，我已经记住你的新名字「{update_nickname}」啦～"

    await add_conversation_history(db, current_user.id, RoleEnum.assistant, final_reply)
    await db.commit()

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