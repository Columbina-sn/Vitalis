# ai/summaryAI.py
from datetime import datetime
from typing import List

from ai.deepseek_client import deepseek_chat_messages
from utills.logging_conf import get_logger

logger = get_logger(__name__)


def build_summary_messages(
    conversations: List[str],   # 按时间正序的对话文本, 每一条格式 "[角色] 内容"
    user_nickname: str = "用户"
) -> list[dict[str, str]]:
    """
    构建总结AI所需的消息列表, 要求模型输出摘要 + 情绪日记 + 关键词.
    conversations 是按时间正序的对话记录文本数组.
    """
    now = datetime.now()
    date_str = now.strftime("%Y年%m月%d日")

    conversation_text = "\n".join(conversations)

    system_prompt = (
        f"今天是{date_str}. 你是小元的记忆助手, 负责将用户一天的对话整理为记忆.\n"
        "你需要输出一个JSON对象, 包含三个字段:\n\n"
        "1. summary: 一句话摘要(不超过100字), 包含用户当天的主要情绪色彩和关键话题."
        "用第三人称描述, 如\"用户今天分享了工作上的压力, 整体情绪有些低落\"."
        "用户性别不确定, 不要随意认定性别, 对用户的描述应中性.\n"
        "2. diary: 一篇150-200字的第二人称情绪日记. 用\"你今天……\"开头, "
        "语气温情但不做作, 像一位了解你的朋友帮你记下的今日心情片段."
        "不要分析或评判, 只是温柔地记录和共情.\n"
        "3. mood_keywords: 3个情绪关键词, 用词精准具体(如\"疲惫但充实\"\"隐隐的焦虑\"\"轻快\"), "
        "不要用\"开心\"\"难过\"这类过于笼统的词.\n\n"
        "输出格式(只输出JSON, 不要其他文字):\n"
        '{"summary": "...", "diary": "...", "mood_keywords": ["关键词1", "关键词2", "关键词3"]}'
    )

    user_message = f"以下是 {user_nickname} 今天的全部对话记录, 请生成记忆:\n\n{conversation_text}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message}
    ]
    return messages


async def generate_daily_summary(
    conversations: List[str],
    user_nickname: str = "用户"
) -> dict:
    """调用DeepSeek生成一天对话的记忆, 返回包含 summary/diary/mood_keywords 的字典."""
    messages = build_summary_messages(conversations, user_nickname)
    try:
        result = await deepseek_chat_messages(messages)
        summary = result.get("summary", "").strip()
        if not summary:
            summary = "暂无有效摘要"
        diary = result.get("diary", "").strip()
        if not diary:
            diary = f"今天{user_nickname}和以前一样, 度过了平常的一天."
        mood_keywords = result.get("mood_keywords", [])
        if not isinstance(mood_keywords, list):
            mood_keywords = []
        logger.debug(f"生成日记成功: {summary[:50]}...")
        return {
            "summary": summary,
            "diary": diary,
            "mood_keywords": mood_keywords
        }
    except Exception as e:
        logger.error(f"生成日记失败: {e}", exc_info=True)
        return {
            "summary": "(摘要生成失败)",
            "diary": "",
            "mood_keywords": []
        }
