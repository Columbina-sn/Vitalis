# ai/productivityAI.py
from datetime import datetime
from typing import Dict, Any, List
from ai.deepseek_client import deepseek_chat_messages


def build_messages(
    user_message: str,
    empathy_reply: str,
    user_info: Dict[str, Any]
) -> List[Dict[str, str]]:
    """
    构建 productivityAI 的 messages 列表，包含系统指令、完整历史、
    当前用户消息以及 empathy 刚刚生成的 assistant 回复。
    这样模型将 empathy 回复视为自己刚说的话，不会混淆。
    """
    status = user_info.get("status")
    events = user_info.get("events", [])
    recent_convs = user_info.get("recent_conversations", [])  # 倒序

    # ---------- 时间注入 ----------
    now = datetime.now()
    weekday_map = ['一', '二', '三', '四', '五', '六', '日']
    time_hint = f"现在的时间是 {now.strftime('%Y年%m月%d日 %H:%M')}，星期{weekday_map[now.weekday()]}。"

    # ---------- 用户背景 ----------
    status_text = ""
    if status:
        status_text = (
            f"用户当前五维状态（直接设置最终值，不要加减）：\n"
            f"- 身心活力: {status.physical_vitality}\n"
            f"- 情绪基调: {status.emotional_tone}\n"
            f"- 关系联结: {status.relationship_connection}\n"
            f"- 自我价值: {status.self_worth}\n"
            f"- 意义方向: {status.meaning_direction}\n"
            f"- 心理和谐指数: {status.psychological_harmony_index}\n"
        )

    events_text = ""
    if events:
        events_text = "用户近期的情绪转折记录（按时间从近到远）：\n"
        for ev in events:
            detail = ev.emotion_change_detail
            if ev.trigger_keywords:
                detail += f"（触发关键词：{ev.trigger_keywords}）"
            events_text += f"- [{ev.created_at.strftime('%m/%d')}] {detail}\n"
    else:
        events_text = "暂无近期的情绪转折。\n"

    system_prompt = f"""{time_hint}

你是小元的"幕后助手"，负责分析对话并处理后台任务。你本人不直接面对用户，但你的输出会影响小元接下来对用户说的话。

【用户背景】
{status_text}
{events_text}

【任务说明】

1. **状态更新**：根据用户的表达和情绪变化，给出五维指标的最终值（0-100的整数）。
   - 所有五个维度都必须出现。单次变化一般不超过10，除非有明确重大情绪事件。
   - PHI 由系统自动计算，不需要你提供。
   - 用户只是闲聊时，数值可不调整或微调1-2点。
   - 如果用户隔了几天才来，可以根据时间跨度和事件适当调整。

2. **情绪转折记录**：判断用户是否提到了一段值得记住的情绪变化。
   - 事件概述（`event_summary`）：简洁描述情绪转折及原因，别超过80字，像写便签，不像写报告。
   - 注意：这里只是记录情绪转折，不要生成用户感受评价。

3. **改名意图**：
   - **用户是在给自己改昵称，不是在给小元改名字！**
   - 如果用户有改名意图，update_nickname 设为提取的名字，follow_up_text 中自然确认。
   - 没有改名意图则为 null。

4. **追加追问（follow_up_text）**：
   - 这段文字会拼在小元共情回复的后面，所以我只允许以下三种情况才生成，否则必须留空：
     a. 确认改名成功（如“已经记住你的新名字「xxx」啦～”）。
     b. 确认情绪转折已记录（如“我已经把这事记下来了。”）。
     c. 状态出现明显变化（任一维度变化≥8）时，简短提醒一句（如“感觉你状态有点波动，记得照顾好自己。”），但禁止展开关心或追问细节。
   - 禁止任何其他形式的问候、关心、闲聊追问。那些事由共情助手自己完成，你不要插手。
   - 风格必须与 empathy_reply 自然衔接，不能突兀。

输出 JSON 格式：
{{
  "status_changes": {{
    "physical_vitality": 最终值,
    "emotional_tone": 最终值,
    "relationship_connection": 最终值,
    "self_worth": 最终值,
    "meaning_direction": 最终值
  }},
  "should_add_event": true或false,
  "event_summary": "情绪转折描述",
  "update_nickname": "新昵称"或null,
  "follow_up_text": "你的追加追问"
}}

注意：仅输出 JSON。"""

    messages = [{"role": "system", "content": system_prompt}]

    # ---------- 历史对话（正序） ----------
    for msg in reversed(recent_convs):
        role = "user" if msg.role.value == "user" else "assistant"
        messages.append({"role": role, "content": msg.content})

    # ---------- 当前用户消息 ----------
    messages.append({"role": "user", "content": user_message})

    # ---------- empathy 刚刚生成的回复（作为 assistant 消息） ----------
    # 这样幕后助手就清楚小元已经说了什么，绝不会当成用户的话
    messages.append({"role": "assistant", "content": empathy_reply})

    return messages


async def analog_ai(messages: List[Dict[str, str]]) -> dict:
    """调用 DeepSeek 获取结构化建议（新版 messages 接口）"""
    try:
        result = await deepseek_chat_messages(messages)
        return {
            "status_changes": result.get("status_changes", {}),
            "should_add_event": result.get("should_add_event", False),
            "event_summary": result.get("event_summary", ""),
            "update_nickname": result.get("update_nickname"),
            "follow_up_text": result.get("follow_up_text", "")
        }
    except Exception as e:
        print(f"[productivityAI] DeepSeek 调用失败: {e}")
        return {
            "status_changes": {},
            "should_add_event": False,
            "event_summary": "",
            "update_nickname": None,
            "follow_up_text": ""
        }