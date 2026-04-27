# routers/chat.py
from datetime import date
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
    add_event,
    add_conversation_history,
    get_conversations_cursor_paginated,
    get_conversations_by_date
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
    # 1. 获取用户完整信息（状态、事件、最近对话）
    user_info = await get_user_full_info(db, current_user.id)
    if user_info is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    # ========== 情感AI（小元的主体回复） ==========
    # 构建标准 messages（含 system 指令 + 历史对话 + 当前用户消息）
    empathy_messages = empathy_build_messages(req.message, user_info)
    empathy_result = await empathy_analog_ai(empathy_messages)
    empathy_reply = empathy_result["reply"]

    # 记录用户消息到对话历史（此时还没提交，后面统一 commit）
    await add_conversation_history(db, current_user.id, RoleEnum.user, req.message)

    # ========== 工作AI（状态、事件、改名、追问） ==========
    # 注意：传入 empathy_reply，让 productivity 也能看到小元刚说的内容
    productivity_messages = productivity_build_messages(
        user_message=req.message,
        empathy_reply=empathy_reply,
        user_info=user_info
    )
    productivity_result = await productivity_analog_ai(productivity_messages)

    # 状态更新
    status_changes = productivity_result["status_changes"]
    if status_changes:
        await update_user_status(db, current_user.id, status_changes)
        updated_status = await get_user_status_by_user_id(db, current_user.id)
        if updated_status:
            status_changes["psychological_harmony_index"] = updated_status.psychological_harmony_index

    # 事件记录
    if productivity_result["should_add_event"]:
        await add_event(
            db,
            current_user.id,
            productivity_result["event_summary"],
            productivity_result["event_evaluation"],
        )

    # ---------- 构建最终回复 ----------
    final_reply = empathy_reply

    follow_up = productivity_result.get("follow_up_text", "").strip()
    if follow_up:
        # 简单过滤一些明显的异常开头
        if follow_up.startswith("你好") or follow_up.startswith("小元"):
            pass
        else:
            final_reply = final_reply.rstrip() + "\n" + follow_up

    # 处理改名请求
    update_nickname = productivity_result.get("update_nickname")
    if update_nickname:
        await update_user_nickname(db, current_user.id, update_nickname)
        if not follow_up or ("记住" not in follow_up and "叫你" not in follow_up):
            final_reply += f"\n好的，我已经记住你的新名字「{update_nickname}」啦～"

    # 记录AI回复到对话历史
    await add_conversation_history(db, current_user.id, RoleEnum.assistant, final_reply)

    await db.commit()

    response_data = {
        "reply": final_reply,
        "status_updates": status_changes,
    }
    return success_response(message="回复用户成功", data=response_data)


@router.get("/history", summary="游标分页获取对话历史记录")
async def get_chat_history(
    before_id: Optional[int] = Query(None, description="游标：上一页最后一条消息的ID，不传则获取最新"),
    page_size: int = Query(20, ge=1, le=50, alias="pageSize", description="每页条数"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    基于游标的分页获取对话记录（按ID倒序，即最新消息在前）
    返回字段：list, hasMore
    """
    records, has_more = await get_conversations_cursor_paginated(
        db,
        current_user.id,
        before_id=before_id,
        limit=page_size
    )

    response_data = {
        "list": [ConversationHistoryResponse.model_validate(rec) for rec in records],
        "hasMore": has_more
    }
    return success_response(message="获取对话记录成功", data=response_data)


@router.get("/history/date", summary="获取当前用户在指定日期的所有对话历史")
async def get_chat_history_by_date(
    target_date: date = Query(..., alias="date", description="查询日期，格式：YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前用户在指定日期的所有对话历史（按时间正序）
    """
    records = await get_conversations_by_date(db, current_user.id, target_date)

    response_data = {
        "list": [ConversationHistoryResponse.model_validate(rec) for rec in records],
        "total": len(records)
    }
    return success_response(message="获取指定日期对话记录成功", data=response_data)