# ai/productivityAI.py
from datetime import datetime
from typing import Dict, Any, List
from ai.deepseek_client import deepseek_chat_messages


def build_messages(
    user_message: str,
    empathy_reply: str,
    user_info: Dict[str, Any]
) -> List[Dict[str, str]]:
    status = user_info.get("status")
    events = user_info.get("events", [])
    recent_convs = user_info.get("recent_conversations", [])
    anchors = user_info.get("anchors", [])
    schedules = user_info.get("upcoming_schedules", [])

    now = datetime.now()
    weekday_map = ['一', '二', '三', '四', '五', '六', '日']
    time_hint = f"现在是{now.strftime('%Y年%m月%d日 %H:%M')}，星期{weekday_map[now.weekday()]}。"

    status_text = ""
    if status:
        status_text = f"当前状态: 身心[{status.physical_vitality}] 情绪[{status.emotional_tone}] 关系[{status.relationship_connection}] 自我[{status.self_worth}] 意义[{status.meaning_direction}] (PHI自动计算)"

    events_text = ""
    if events:
        events_text = "近期情绪转折: " + " | ".join(
            f"[{ev.created_at.strftime('%m/%d')}] {ev.emotion_change_detail[:50]}" for ev in events
        )

    anchors_text = ""
    if anchors:
        anchors_text = "现有画像: " + ", ".join(
            f"{a.anchor_type}:{a.content}({a.confidence:.1f})" for a in anchors
        )
    else:
        anchors_text = "暂无画像"

    schedules_text = ""
    if schedules:
        schedules_text = "现有日程: " + ", ".join(
            f"{sc.schedule_type}:{sc.title}({sc.scheduled_time.strftime('%m/%d') if sc.scheduled_time else '无期'})" for sc in schedules
        )
    else:
        schedules_text = "暂无日程"

    system_prompt = f"""{time_hint}
【角色】你是小元的后台分析器，只输出结构化数据，不参与对话。

【五维定义（避免歧义）】
{status_text}
- physical_vitality：身体健康/精力/疲劳感 （高=状态好，低=生病/疲惫）
- emotional_tone：情绪基调/心理压力 （高=积极/快乐，低=悲伤/焦虑/愤怒）
- relationship_connection：社会联结/被支持感（高=关系好，低=孤独/疏离）
- self_worth：自我价值感/成就感 （高=自信，低=自我否定）
- meaning_direction：目标意义感/未来期待 （高=清晰/期待，低=迷茫）
调整原则：当用户直接表达身体或情绪的强烈变化（如“发烧”“崩溃”“狂喜”）时，立即将对应维度拉到与表达一致的数值（范围 0-100，可跨越 40+），不要平滑过渡。日常杂谈微调 1-3 点。

【任务与输出规范】
1. status_changes：必须用英文key给出5个维度的最终值（0-100整数）。
2. 情绪转折：若本轮对话中有明确的值得记录的情绪起伏，用 ≤50 字概括为 event_summary，设 should_add_event=true。
3. 改名意图：从本轮对话提取用户**给自己**换的新昵称，填到 update_nickname；若用户只是在给你起外号、描述你或称呼你（语句主语/宾语是“你/小元/小鸽子”等），则 update_nickname 一律为 null。
4. follow_up_text：**仅限**对改名/日程/情绪转折的确认文字（如 已记下新昵称：xxx。 已记录新日程：类型（时间）：内容 等），或维度变化≥8时的一句客观事实陈述（≤20字，**不得包含问号、建议、关心**）。不询问用户、不延展对话。
5. 用户画像：若用户表达的是稳定的个人特质、价值观或长期习惯，可创建/更新 anchors。new_anchors 必须是对象数组，每项含 anchor_type, content, confidence(0-1)。
6. 日程创建：识别对话中任何表示未来时间节点的表达，立即创建日程。**一次可创建多个日程**，字段为 new_schedules（数组）。每个日程含 schedule_type (short_task/long_goal/countdown/anniversary/birthday)、title、description、scheduled_time（格式 YYYY-MM-DDTHH:MM 或 null）。若同一意图已存在则跳过。
7. 防重复：与最近1小时记录重复则不创建。

输出 JSON：
{{
  "status_changes": {{"physical_vitality": 60, "emotional_tone": 75, "relationship_connection": 80, "self_worth": 65, "meaning_direction": 85}},
  "should_add_event": false,
  "event_summary": "",
  "update_nickname": null,
  "follow_up_text": "",
  "should_update_anchors": false,
  "new_anchors": [],
  "should_create_schedule": false,
  "new_schedules": [
    {{"schedule_type":"short_task","title":"示例日程","description":"示例描述","scheduled_time":"2026-05-01T00:00"}}
  ]
}}
只输出 JSON。"""

    messages = [{"role": "system", "content": system_prompt}]
    for msg in reversed(recent_convs):
        role = "user" if msg.role.value == "user" else "assistant"
        messages.append({"role": role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    messages.append({"role": "assistant", "content": empathy_reply})
    return messages


async def analog_ai(messages: List[Dict[str, str]]) -> dict:
    try:
        result = await deepseek_chat_messages(messages)
        return {
            "status_changes": result.get("status_changes", {}),
            "should_add_event": result.get("should_add_event", False),
            "event_summary": result.get("event_summary", ""),
            "update_nickname": result.get("update_nickname"),
            "follow_up_text": result.get("follow_up_text", ""),
            "should_update_anchors": result.get("should_update_anchors", False),
            "new_anchors": result.get("new_anchors", []),
            "should_create_schedule": result.get("should_create_schedule", False),
            "new_schedules": result.get("new_schedules", []),   # 改为数组
        }
    except Exception as e:
        print(f"[productivityAI] DeepSeek 调用失败: {e}")
        return {
            "status_changes": {},
            "should_add_event": False,
            "event_summary": "",
            "update_nickname": None,
            "follow_up_text": "",
            "should_update_anchors": False,
            "new_anchors": [],
            "should_create_schedule": False,
            "new_schedules": [],
        }