# ai/memory/context_manager.py
"""上下文管理器：为共情 AI / 工作 AI 组装上下文，触发 15 轮压缩。

职责：
- 从 HistoryStore 读取压缩摘要 + 近期消息
- 为共情 AI 组装全量上下文（压缩历史摘要 + 近期消息）
- 为工作 AI 提供精简上下文（仅最近 N 条消息）
- 对话完成后存储消息并检查是否触发影子 AI 压缩
"""

from datetime import datetime
from typing import Optional

from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from ai.llm import get_shadow_llm
from ai.memory.history_store import HistoryStore
from utills.logging_conf import get_logger

logger = get_logger(__name__)

# ---------- 影子 AI 压缩 Prompt ----------
COMPRESSION_SYSTEM_PROMPT = """你是小元的记忆助手。你的任务是将用户与小元（一个AI陪伴伙伴）的对话历史压缩为密集摘要。

要求：
1. 保留关键话题和事件（如"用户在准备期末考试""和室友发生了矛盾"）
2. 保留情绪脉络（如"从焦虑→逐渐平静→重新振作"）
3. 保留重要事实（如用户偏好、习惯、提到的人名/地名）
4. 保留小元给过的重要建议或用户表示认可的回应
5. 第三人称描述，不超过 500 字
6. 只输出摘要文本，不要 JSON 或其他格式

请生成压缩摘要："""


class ContextManager:

    COMPRESSION_THRESHOLD = 15  # 每 15 轮触发压缩

    def __init__(self, store: HistoryStore):
        self.store = store

    # ---------- 上下文组装 ----------

    async def get_empathy_context(self, user_id: int) -> dict:
        """为共情 AI 组装全量上下文。

        Returns:
            dict with:
              - summary_text: 压缩历史摘要文本（注入 system prompt 用）
              - history_messages: 近期消息的 LangChain BaseMessage 列表
        """
        raw = await self.store.get_context(user_id)

        # 组装压缩摘要文本
        summary_parts = []
        if raw["compressed_summaries"]:
            summary_parts.append("【之前的对话摘要（按时间顺序）】")
            for s in raw["compressed_summaries"]:
                summary_parts.append(f"  · {s}")
        summary_text = "\n".join(summary_parts) if summary_parts else ""

        # 将近期消息转为 LangChain 消息对象
        history_messages: list[BaseMessage] = []
        for msg in raw["recent_messages"]:
            if msg["role"] == "user":
                history_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                history_messages.append(AIMessage(content=msg["content"]))

        return {
            "summary_text": summary_text,
            "history_messages": history_messages,
        }

    async def get_productivity_context(self, user_id: int, n: int = 4) -> list[dict]:
        """为工作 AI 提供精简上下文（仅最近 n 条消息的原始 dict）。"""
        return await self.store.get_recent_messages(user_id, n)

    # ---------- 对话后处理 ----------

    async def after_conversation(
        self,
        user_id: int,
        user_msg: str,
        assistant_msg: str,
    ):
        """对话完成后的后处理。

        存储本轮消息 → 递增轮数 → 检查是否需要触发压缩。
        压缩是异步 fire-and-forget 的（不阻塞用户响应）。
        """
        await self.store.add_message(user_id, "user", user_msg)
        await self.store.add_message(user_id, "assistant", assistant_msg)
        await self.store.increment_round(user_id)

        rounds = await self.store.get_rounds_since_compression(user_id)
        if rounds >= self.COMPRESSION_THRESHOLD:
            # 异步触发压缩，不阻塞当前请求
            logger.info(f"用户 {user_id} 达到 {rounds} 轮，触发上下文压缩")
            await self._trigger_compression(user_id)

    # ---------- 内部：压缩逻辑 ----------

    async def _trigger_compression(self, user_id: int):
        """调用影子 AI 压缩对话历史"""
        try:
            raw = await self.store.get_context(user_id)

            # 构建压缩输入：已有摘要 + 近期消息的文本表示
            conversation_text_parts = []

            if raw["compressed_summaries"]:
                conversation_text_parts.append("=== 之前已压缩的摘要 ===")
                for s in raw["compressed_summaries"]:
                    conversation_text_parts.append(s)

            if raw["recent_messages"]:
                conversation_text_parts.append("\n=== 最近的对话 ===")
                for msg in raw["recent_messages"]:
                    role_label = "用户" if msg["role"] == "user" else "小元"
                    conversation_text_parts.append(f"[{role_label}] {msg['content']}")

            conversation_text = "\n".join(conversation_text_parts)

            if not conversation_text.strip():
                logger.warning(f"用户 {user_id} 无对话内容可压缩")
                return

            # 调用影子 AI
            llm = get_shadow_llm()
            response = await llm.ainvoke([
                {"role": "system", "content": COMPRESSION_SYSTEM_PROMPT},
                {"role": "user", "content": f"以下是要压缩的对话历史：\n\n{conversation_text}"},
            ])
            summary_text = response.content.strip()

            if not summary_text:
                logger.warning(f"用户 {user_id} 影子 AI 返回空摘要")
                return

            # 存储压缩结果
            await self.store.compress(user_id, summary_text)
            logger.info(f"用户 {user_id} 上下文压缩完成 ({len(summary_text)} 字)")

        except Exception as e:
            logger.error(f"用户 {user_id} 上下文压缩失败: {e}", exc_info=True)
            # 压缩失败不影响对话流程——下次对话时再试
