# ai/productivityAI.py
from datetime import datetime
from typing import Dict, Any, List
from ai.deepseek_client import deepseek_chat_messages


def build_messages(
    user_message: str,
    user_info: Dict[str, Any]
) -> List[Dict[str, str]]:
    status = user_info.get("status")
    emotion_shifts = user_info.get("emotion_shifts", [])
    recent_convs = user_info.get("recent_conversations", [])
    anchors = user_info.get("anchors", [])
    schedules = user_info.get("upcoming_schedules", [])  # 仍可传递未来日程作背景

    now = datetime.now()
    weekday_map = ['一', '二', '三', '四', '五', '六', '日']
    time_hint = f"现在是{now.strftime('%Y年%m月%d日 %H:%M')}，星期{weekday_map[now.weekday()]}。"

    status_text = ""
    if status:
        status_text = f"当前状态: 身心[{status.physical_vitality}] 情绪[{status.emotional_tone}] 关系[{status.relationship_connection}] 自我[{status.self_worth}] 意义[{status.meaning_direction}] (PHI自动计算)"

    emotion_shifts_text = ""
    if emotion_shifts:
        emotion_shifts_text = "近期情绪转折: " + " | ".join(
            f"[{ev.created_at.strftime('%m/%d')}] {ev.emotion_change_detail[:50]}" for ev in emotion_shifts
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
【角色】你是小元的后台分析助手，只输出结构化数据，不参与对话。

【五维定义（避免歧义）】
用户上次状态：
{status_text}
- physical_vitality：身体健康/精力/疲劳感 （高=状态好，低=生病/疲惫）
- emotional_tone：情绪基调/心理压力 （高=积极/快乐，低=悲伤/焦虑/愤怒）
- relationship_connection：社会联结/被支持感（高=关系好，低=孤独/疏离）
- self_worth：自我价值感/成就感 （高=自信，低=自我否定）
- meaning_direction：目标意义感/未来期待 （高=清晰/期待，低=迷茫）
调整原则：当用户直接表达身体或情绪的强烈变化（如“发烧”“崩溃”“狂喜”）时，立即将对应维度拉到与表达一致的数值（范围 0-100，可跨越 40+），不要平滑过渡。日常杂谈微调 1-3 点。

【任务与输出规范】
1. status_changes：必须用英文key给出5个维度的最终值（0-100整数）。

用户最近情绪转变
{emotion_shifts_text}
2. 情绪转折：若本轮对话中有明确的值得记录的情绪起伏，用 ≤50 字概括为 emotion_shifts_summary，设 should_add_emotion_shifts=true。

3. 改名意图：从本轮对话提取用户**给自己**换的新昵称，填到 update_nickname；若用户只是在给你起外号、描述你或称呼你，则 update_nickname 一律为 null，你只能给用户改昵称。
4. follow_up_text：**仅限**对改名/日程/情绪转折的确认文字（如 已记下新昵称：xxx。 已记录新日程：类型（时间）：内容 等），或一张表格维度变化≥8时的一句简短的客观事实陈述（**不得包含任何问句、建议、关心、追问、开启新话题等**）。当且仅当需要用户确认编辑/删除日程时，可以包含一个简短问句（如“需要我删除‘散步’这个日程吗？”），但不能展开对话。

用户现有画像（部分）：
{anchors_text}
5. 用户画像：若用户表达的是稳定的个人特质、价值观或长期习惯，可创建/更新 anchors。new_anchors 必须是对象数组，每项含 anchor_type, content, confidence(0~1，你的确信程度)。

用户现有日程如下：（如需编辑、删除，必须在下列日程中挑选准确title）
{schedules_text}
6. 日程创建：识别对话中任何表示未来时间节点的表达，立即创建日程。**一次可创建多个日程**，字段为 new_schedules（数组）。每个日程含 schedule_type (short_task/long_goal/countdown/anniversary/birthday)、title、description、scheduled_time（格式 YYYY-MM-DDTHH:MM 或 null）。若同一意图已存在则跳过。
7. 日程编辑：当用户要求修改现有日程（例如改时间、改名称），或认为某日程因理解错误而需要修正时，应输出 schedule_edits（数组）。每项必须包含 **title**（当前日程标题，用于匹配），然后至少包含一个修改字段：new_title、new_description、new_scheduled_time、new_type、new_completed。如果用户说“任务完成了”，请将 new_completed 设为 true，而不是直接删除。如果用户明确要求删除，请走“日程删除”规则。
8. 日程删除：当用户明确要删除某个日程，或系统判断某个倒数日已过、生日已过、纪念日已过，或者某个短期任务已无意义时，可以输出 schedule_deletes（数组）。每项必须包含 **title**（当前日程标题，用于匹配）。请注意：系统会自动模糊匹配标题，但若你无法确定原标题，可留空并在 follow_up_text 中询问用户。
9. 防重复：与最近1小时记录重复则不创建。

【日程编辑与删除的匹配说明（你必须理解）】
- 后端会先将你输出的 title 与用户实际日程标题进行精确匹配。
- 若精确匹配失败，会使用模糊匹配（相似度≥70%的最近似项）。
- 因此，你输出的 title 应尽可能与用户原始日程标题一致（可以从对话中推断,但实际用名必须为现有日程有的）。若完全不确定，就不要填写 title，而是在 follow_up_text 中询问用户。

输出 JSON：
{{
  "status_changes": {{"physical_vitality": 60, "emotional_tone": 75, "relationship_connection": 80, "self_worth": 65, "meaning_direction": 85}},
  "should_add_emotion_shifts": false,
  "emotion_shifts_summary": "",
  "update_nickname": null,
  "follow_up_text": "",
  "should_update_anchors": false,
  "new_anchors": [],
  "should_create_schedule": false,
  "new_schedules": [
    {{"schedule_type":"short_task","title":"示例日程","description":"示例描述","scheduled_time":"2026-05-01T00:00"}}
  ],
  "schedule_edits": [
    {{"title":"旧的标题","new_title":"新的标题","new_completed":true}}
  ],
  "schedule_deletes": [
    {{"title":"要删除的标题"}}
  ]
}}
只输出 JSON。"""

    messages = [{"role": "system", "content": system_prompt}]
    for msg in reversed(recent_convs):
        role = "user" if msg.role.value == "user" else "assistant"
        messages.append({"role": role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    messages.append({"role": "assistant", "content": "[同步处理中，请忽略]"})
    return messages


async def analog_ai(messages: List[Dict[str, str]]) -> dict:
    try:
        result = await deepseek_chat_messages(messages, temperature=0.25)
        return {
            "status_changes": result.get("status_changes", {}),
            "should_add_emotion_shifts": result.get("should_add_emotion_shifts", False),
            "emotion_shifts_summary": result.get("emotion_shifts_summary", ""),
            "update_nickname": result.get("update_nickname"),
            "follow_up_text": result.get("follow_up_text", ""),
            "should_update_anchors": result.get("should_update_anchors", False),
            "new_anchors": result.get("new_anchors", []),
            "should_create_schedule": result.get("should_create_schedule", False),
            "new_schedules": result.get("new_schedules", []),
            "schedule_edits": result.get("schedule_edits", []),
            "schedule_deletes": result.get("schedule_deletes", []),
        }
    except Exception as e:
        print(f"[productivityAI] DeepSeek 调用失败: {e}")
        return {
            "status_changes": {},
            "should_add_emotion_shifts": False,
            "emotion_shifts_summary": "",
            "update_nickname": None,
            "follow_up_text": "",
            "should_update_anchors": False,
            "new_anchors": [],
            "should_create_schedule": False,
            "new_schedules": [],
            "schedule_edits": [],
            "schedule_deletes": [],
        }