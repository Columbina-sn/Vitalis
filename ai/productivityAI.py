# ai/productivityAI.py
from datetime import datetime
from typing import Dict, Any, List
from ai.deepseek_client import deepseek_chat_messages


def build_messages(
    user_message: str,
    user_info: Dict[str, Any]
) -> List[Dict[str, str]]:
    """构建工作 AI 的 messages，只输出结构化 JSON，不参与对话。"""
    status = user_info.get("status")
    emotion_shifts = user_info.get("emotion_shifts", [])
    anchors = user_info.get("anchors", [])
    schedules = user_info.get("upcoming_schedules", [])
    completed_schedules = user_info.get("recent_completed_schedules", [])
    recent_convs = user_info.get("recent_conversations", [])

    # ---- 提取最近 2 条用户消息，用于帮助工作 AI 理解编辑/删除所指 ----
    recent_user_lines = []
    for msg in recent_convs:
        if msg.role.value == 'user':
            recent_user_lines.append(msg.content)
            if len(recent_user_lines) >= 2:
                break
    # recent_convs 是倒序，这里取到的是从最近往前数两条，我们需要按时间正序（最早的在前）
    if recent_user_lines:
        recent_user_lines = list(reversed(recent_user_lines))   # 最早发言 → 最新发言
        recent_user_lines.append(user_message)
        recent_user_text = "用户最近的发言(从早到晚):\n" + "\n".join(
            f"    {i+1}. {line}" for i, line in enumerate(recent_user_lines)
        )
    else:
        recent_user_text = ""

    now = datetime.now()
    weekday_map = ['一', '二', '三', '四', '五', '六', '日']
    time_hint = f"现在是{now.strftime('%Y年%m月%d日 %H:%M')}，星期{weekday_map[now.weekday()]}。"

    # 状态文本
    status_text = ""
    if status:
        status_text = (
            f"当前五维状态: 身心活力={status.physical_vitality}, "
            f"情绪基调={status.emotional_tone}, 关系联结={status.relationship_connection}, "
            f"自我价值={status.self_worth}, 意义方向={status.meaning_direction}。"
            f"PHI（心理和谐指数）会自动计算，无需你处理。"
        )

    # 情绪转折
    shifts_text = ""
    if emotion_shifts:
        shifts_text = "近期情绪转折: " + " | ".join(
            f"[{ev.created_at.strftime('%m/%d')}] {ev.emotion_change_detail}"
            for ev in emotion_shifts[:3]
        )

    # 用户画像
    anchors_text = ""
    if anchors:
        anchors_text = "现有画像: " + ", ".join(
            f"{a.anchor_type}:{a.content}(置信度{a.confidence:.1f})" for a in anchors
        )
    else:
        anchors_text = "暂无画像"

    # 未完成日程
    schedules_text = ""
    if schedules:
        schedules_text = "未完成日程: " + ", ".join(
            f"{sc.schedule_type},title:{sc.title}"
            f"({sc.scheduled_time.strftime('%Y年%m月%d日') if sc.scheduled_time else '无固定日期'})"
            for sc in schedules
        )
    else:
        schedules_text = "暂无未完成日程"

    # 已完成日程 (背景)
    comp_text = ""
    if completed_schedules:
        comp_text = "已完成日程(仅供背景参考, 非用户命令不要随意操作): " + ", ".join(
            f"{sc.schedule_type},title:{sc.title}" for sc in completed_schedules[:5]
        )

    # 日程操作警告：没有未完成日程时禁止编辑/删除
    no_sched_warn = ""
    if not schedules:
        no_sched_warn = "\n⚠️ 当前没有未完成日程。禁止输出 schedule_edits 或 schedule_deletes。"

    system_prompt = f"""{time_hint}

你是小元的后台分析助手。你的任务是根据本轮用户消息，完成以下结构化决策，并只输出一个 JSON 对象。
你绝对不能输出除 JSON 以外的任何文字。

【输入数据】
用户消息: "{user_message}"
{status_text}
{shifts_text}
{anchors_text}
{schedules_text}{no_sched_warn}
{comp_text}

【你需要做出以下判断（全部封装在 JSON 内）】

1. **五维状态调整** (`status_changes`)
   - 必须包含5个键: physical_vitality, emotional_tone, relationship_connection, self_worth, meaning_direction，值为整数(0-100)。
   - 原则: 用户表达明确身体/情绪等变化时立刻大幅度调整(可跨40+点)；
          日常闲聊内容只要正常不悲观伤感，缓慢增加2-5点，尤其用户只要短期内并不表现负面情绪，不要让数值长期停在60以下；
          若未涉及则保持原值。
   - 不要输出 PHI，PHI由后台结合五维数值计算。
   - 五维的理想点位为"physical": 80, "emotional": 75, "relation": 80, "worth": 85, "meaning": 75。

2. **情绪转折记录** (`should_add_emotion_shifts`, `emotion_shifts_summary`)
   - 如果本轮对话包含明显的值得记录的情绪起伏，用≤50字概括，并设 should_add_emotion_shifts=true。

3. **改名意图** (`update_nickname`)
   - 如果用户明确为自己更换昵称，提取新昵称（包含·等特殊字符请尽量完整），否则为 null。
   - 你们就是小元，不给自己改名。

4. **用户画像更新** (`should_update_anchors`, `new_anchors`)
   - 如果用户表达了稳定的个人特质、价值观或长期习惯，可创建/更新画像。
   - new_anchors 是对象数组，每项包含 anchor_type, content, confidence(0~1)。
   - 注意 confidence 不要轻易给高，尤其是负面内容（会影响后续ai工作）。

5. **日程管理**
   - 创建 (`should_create_schedule`, `new_schedules`): 识别未来时间节点，**必须使用当前时间进行推断**。可一次创建多个。
     {time_hint}
     - “明天”“后天”“下周X”等表达 → 计算出精确日期（格式 YYYY-MM-DD）。
     - 若有具体钟点（如“下午三点”“晚上八点”）→ 映射为24小时制（15:00、20:00），填入 YYYY-MM-DDTHH:MM。
     - 若只有日期没有钟点 → 默认使用 **09:00**（如 "2026-05-05T09:00"）。
     - 如果完全没有时间指向（如“我要复习”且未提何时）→ scheduled_time 设为 **null**。
     - 过滤原则：如果用户描述的只是当下的抱怨、临时安排或无法回避的杂事，且语气明显消极（如“义务”“无奈”“被拉去”等），不要创建日程。日程应留给用户真正想完成或记住的事项。
     
   用户最近部分日程：（如需编辑删除，必须在下列日程中选title，不要被用户消息干扰！）
   {schedules_text}
   {comp_text}
   - 编辑 (`schedule_edits`): 若用户要求修改已有日程，每项包含 title(原标题，用于匹配)、new_title、new_description、new_scheduled_time、new_type、new_completed 等要修改的字段。可一次编辑多个。
     * 如果用户没有指明具体标题，但结合“用户最近的发言”可以推断所指的是哪条日程，请填写对应的 title。
     {recent_user_text}

   - 删除 (`schedule_deletes`): 若用户要求删除，每项包含 title。可一次删除多个。
     * 如果用户没有指明具体标题，但结合“用户最近的发言”可以推断所指的是哪条日程，请填写对应的 title。
     {recent_user_text}

   - 防重复/防误操作：如果同一内容在最近1小时内已存在则跳过；编辑/删除仅在 schedules 列表中存在对应标题时进行，若不确认标题可以留空 title，但不能瞎编。

【输出 JSON 模板】
{{
  "status_changes": {{"physical_vitality": 60, "emotional_tone": 75, "relationship_connection": 80, "self_worth": 65, "meaning_direction": 85}},
  "should_add_emotion_shifts": false,
  "emotion_shifts_summary": "",
  "update_nickname": null,
  "should_update_anchors": false,
  "new_anchors": [],
  "should_create_schedule": false,
  "new_schedules": [
    {{"schedule_type":"short_task","title":"示例","description":"","scheduled_time":"2026-05-05T10:00"}}
  ],
  "schedule_edits": [
    {{"title":"旧标题","new_title":"新标题","new_completed":true}}
  ],
  "schedule_deletes": [
    {{"title":"要删除的标题"}}
  ]
}}

只输出 JSON。"""

    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}]
    return messages


async def analog_ai(messages: List[Dict[str, str]]) -> dict:
    """调用工作 AI，返回结构化字典（无 follow_up_text）"""
    try:
        result = await deepseek_chat_messages(messages, temperature=0.2)
    except Exception as e:
        print(f"[productivityAI] 调用失败: {e}")
        return _fallback_result()

    return {
        "status_changes": result.get("status_changes", {}),
        "should_add_emotion_shifts": result.get("should_add_emotion_shifts", False),
        "emotion_shifts_summary": result.get("emotion_shifts_summary", ""),
        "update_nickname": result.get("update_nickname"),
        "should_update_anchors": result.get("should_update_anchors", False),
        "new_anchors": result.get("new_anchors", []),
        "should_create_schedule": result.get("should_create_schedule", False),
        "new_schedules": result.get("new_schedules", []),
        "schedule_edits": result.get("schedule_edits", []),
        "schedule_deletes": result.get("schedule_deletes", []),
    }


def _fallback_result() -> dict:
    return {
        "status_changes": {},
        "should_add_emotion_shifts": False,
        "emotion_shifts_summary": "",
        "update_nickname": None,
        "should_update_anchors": False,
        "new_anchors": [],
        "should_create_schedule": False,
        "new_schedules": [],
        "schedule_edits": [],
        "schedule_deletes": [],
    }