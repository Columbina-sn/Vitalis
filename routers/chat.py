# routers/chat.py
from datetime import date, datetime as dt
from typing import Optional

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
    # 1. 获取紧凑版用户信息
    user_info = await get_user_full_info(db, current_user.id)
    if user_info is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    # 2. 情感AI
    empathy_messages = empathy_build_messages(req.message, user_info)
    print(f"情感提示词{empathy_messages}")
    empathy_result = await empathy_analog_ai(empathy_messages)
    print(f"情感回应{empathy_result}")
    empathy_reply = empathy_result["reply"]

    await add_conversation_history(db, current_user.id, RoleEnum.user, req.message)

    # 3. 工作AI
    productivity_messages = productivity_build_messages(
        user_message=req.message,
        empathy_reply=empathy_reply,
        user_info=user_info,
    )
    print(f"工作提示词{productivity_messages}")
    prod_result = await productivity_analog_ai(productivity_messages)
    print(f"工作回应{prod_result}")

    # 4. 更新状态
    status_changes = prod_result.get("status_changes", {})
    if status_changes:
        await update_user_status(db, current_user.id, status_changes)
        updated_status = await get_user_status_by_user_id(db, current_user.id)
        if updated_status:
            status_changes["psychological_harmony_index"] = updated_status.psychological_harmony_index

    # 5. 记录情绪转折（防重）
    if prod_result.get("should_add_event") and prod_result["event_summary"]:
        is_duplicate = await check_recent_duplicate_emotion_shift(db, current_user.id, prod_result["event_summary"])
        if not is_duplicate:
            await add_emotion_shift(
                db,
                current_user.id,
                emotion_change_detail=prod_result["event_summary"],
                trigger_keywords=None
            )

    # 6. 处理用户画像更新
    if prod_result.get("should_update_anchors") and prod_result["new_anchors"]:
        for anchor_data in prod_result["new_anchors"]:
            # 容错：如果 AI 直接返回了字符串，则包装为 {"content": 字符串, "anchor_type": "note"}
            if isinstance(anchor_data, str):
                anchor_data = {"content": anchor_data, "anchor_type": "note", "confidence": 0.5}
            await add_or_update_memory_anchor(
                db,
                current_user.id,
                anchor_type=anchor_data.get("anchor_type", "note"),
                content=anchor_data.get("content", ""),
                confidence=anchor_data.get("confidence", 0.5),
            )

    # 7. 创建日程（支持批量）
    if prod_result.get("should_create_schedule") and prod_result.get("new_schedules"):
        for sched in prod_result["new_schedules"]:
            if not sched.get("title"):
                continue
            already_exists = await check_recent_similar_schedule(
                db, current_user.id, sched.get("schedule_type", ""), sched.get("title", "")
            )
            if not already_exists:
                scheduled_time = None
                raw_time = sched.get("scheduled_time")
                if raw_time and isinstance(raw_time, str):
                    try:
                        scheduled_time = dt.fromisoformat(raw_time)
                    except ValueError:
                        print(f"[日程解析] 忽略非法时间格式: {raw_time}")
                await create_schedule(
                    db,
                    current_user.id,
                    schedule_type=sched.get("schedule_type", "short_task"),
                    title=sched.get("title", ""),
                    description=sched.get("description"),
                    scheduled_time=scheduled_time,
                )

    # 8. 构建最终回复
    final_reply = empathy_reply
    follow_up = prod_result.get("follow_up_text", "").strip()
    if follow_up and not follow_up.startswith(("你好", "小元")):
        final_reply = final_reply.rstrip() + "\n\n" + follow_up

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