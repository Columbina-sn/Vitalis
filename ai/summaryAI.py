# ai/summaryAI.py
from datetime import datetime
from typing import List

from ai.deepseek_client import deepseek_chat_messages


def build_summary_messages(
    conversations: List[str],   # 按时间正序的对话文本，每一条格式 "[角色] 内容"
    user_nickname: str = "用户"
) -> list[dict[str, str]]:
    """
    构建总结AI所需的消息列表，要求模型输出一句话情绪摘要（不超过100字）。
    conversations 是按时间正序的对话记录文本数组。
    """
    now = datetime.now()
    date_str = now.strftime("%Y年%m月%d日")

    conversation_text = "\n".join(conversations)

    system_prompt = (
        f"今天是{date_str}。你是小元的记忆助手，负责将用户一天的对话浓缩成一句简洁的摘要。\n"
        "要求：\n"
        "1. 摘要必须包含用户当天的主要情绪色彩（如开心、疲惫、焦虑、平静等）和关键话题。\n"
        "2. 不要超过100字，像一句日记。\n"
        "3. 用第三人称描述，例如“用户今天分享了工作上的压力，整体情绪有些低落”。\n"
        "4. 不要出现“摘要”字样，直接给出内容。\n"
        "5. 用户性别不确定，不要随意认定性别，对用户的描述应中性。\n"
        "输出格式：\n"
        '{"summary": "你的摘要内容"}'
    )

    user_message = f"以下是 {user_nickname} 今天的全部对话记录，请生成记忆摘要：\n\n{conversation_text}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    return messages


async def generate_daily_summary(
    conversations: List[str],
    user_nickname: str = "用户"
) -> str:
    """调用DeepSeek生成一天对话的摘要，返回summary字符串。"""
    messages = build_summary_messages(conversations, user_nickname)
    try:
        result = await deepseek_chat_messages(messages)
        summary = result.get("summary", "").strip()
        if not summary:
            summary = "暂无有效摘要"
        return summary
    except Exception as e:
        print(f"[summaryAI] 生成摘要失败: {e}")
        return "（摘要生成失败）"