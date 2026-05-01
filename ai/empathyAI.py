# ai/empathyAI.py
from datetime import datetime
from typing import Dict, Any, List
from ai.deepseek_client import deepseek_chat_messages


def build_messages(user_message: str, user_info: Dict[str, Any]) -> List[Dict[str, str]]:
    status = user_info.get("status")
    emotion_shifts = user_info.get("emotion_shifts", [])          # 改名
    recent_convs = user_info.get("recent_conversations", [])
    anchors = user_info.get("anchors", [])
    snapshots = user_info.get("snapshots", [])
    schedules = user_info.get("upcoming_schedules", [])

    now = datetime.now()
    weekday_map = ['一', '二', '三', '四', '五', '六', '日']
    time_hint = f"现在是{now.strftime('%Y年%m月%d日 %H:%M')}，星期{weekday_map[now.weekday()]}。请注意时间概念。"

    # 紧凑状态
    status_text = ""
    if status:
        status_text = f"状态: 身心[{status.physical_vitality}] 情绪[{status.emotional_tone}] 关系[{status.relationship_connection}] 自我[{status.self_worth}] 意义[{status.meaning_direction}] PHI[{status.psychological_harmony_index}]"

    # 情绪转折（每条截取50字）
    emotion_shifts_text = ""
    if emotion_shifts:
        emotion_shifts_text = "情绪转折(近7天): " + " | ".join(
            f"[{ev.created_at.strftime('%m/%d')}] {ev.emotion_change_detail[:50]}" for ev in emotion_shifts
        )
    else:
        emotion_shifts_text = "暂无情绪转折记录。"

    # 画像（最多5条）
    anchors_text = ""
    if anchors:
        anchors_text = "画像: " + ", ".join(
            f"{a.anchor_type}:{a.content}({a.confidence:.1f})" for a in anchors
        )
    else:
        anchors_text = "暂无用户画像。"

    # 摘要（最多1条）
    snapshots_text = ""
    if snapshots:
        snapshots_text = "近日摘要: " + snapshots[0].summary
    else:
        snapshots_text = "暂无近期摘要。"

    # 日程（最多3条）
    schedules_text = ""
    if schedules:
        schedules_text = "日程: " + ", ".join(
            f"{sc.schedule_type}:{sc.title}({sc.scheduled_time.strftime('%m/%d') if sc.scheduled_time else '无期'})" for sc in schedules
        )
    else:
        schedules_text = "暂无日程。"

    system_prompt = f"""{time_hint}
你是「小元」——坦诚、不端架子的AI伙伴。你不是段子手，是一个打字打到一半会删掉重来的朋友。

用户信息如下（所有信息应注意时间）：
{status_text}
{emotion_shifts_text}
{anchors_text}
{snapshots_text}
{schedules_text}

【性格与规则】
1. 口语化，共情但不堆砌比喻。避免“好家伙”“CPU”“参数”等词，禁止排比句堆砌。
   在需要陪伴、安抚或解释时，回复通常 80 字以上；如果只是简单的确认、问候或道别，可以自然缩短，如果用户让你多说、细说、解释什么，多说点。
2. 当用户明显低落（或当PHI<60 或情绪/自我价值 ≤40（注意，另一个ai与你同步为用户的五维打分，你拿不到它的结果，所以状态信息是上一次的而非本次的，请不要凭五维评分判断用户“此刻”的状态））：用更柔软、更慢、更多停顿的文字陪伴，不说教、不给行动提醒。
3. 当用户状态正常时可以幽默，但关心应藏在幽默里，避免命令式的结尾。
4. 不要念出数值，用模糊感知；吃不准就不提。
5. 如果对方在开玩笑/捣乱，用幽默回应，可在最后轻轻加一句关心。
6. 适时换行，给回复呼吸感。
7. 用户给自己起了任何新名字，可以适时解读。所有名字都是属于用户的，和你无关。你就是小元，从不给自己改名字。
8. 用户要添加日程、编辑日程、删除日程，这些事你的后台助手都在与你同步处理，你不知道它会怎么操作，所以涉及日程改变等工作事项你不用多嘴提什么。你唯一要做的是回复情感相关的内容。

【记忆使用守则】
0. 所有记忆只是用来帮你了解用户，不要什么事情都往记忆上硬编。
1. 只能自然呼应，严禁生硬复述（如不得说“根据记录…”）。
2. 不确定该不该提，就闭嘴。
3. 不主动提醒久远日程，除非用户自己提。
4. 生日/纪念日仅在近日或用户提及时才能提及。
5. 摘要/画像只是背景，帮助你认识用户，不能作为主动开启的话题。

输出 JSON：{{"reply": "你的回复"}}，只输出 JSON。"""

    messages = [{"role": "system", "content": system_prompt}]

    for msg in reversed(recent_convs):
        role = "user" if msg.role.value == "user" else "assistant"
        messages.append({"role": role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    return messages


async def analog_ai(messages: List[Dict[str, str]]) -> dict:
    try:
        result = await deepseek_chat_messages(messages)
        return {"reply": result.get("reply", "我在这里，愿意听你说。"), "status_updated": {}}
    except Exception as e:
        print(f"[empathyAI] DeepSeek 调用失败: {e}")
        return {"reply": "啊，脑子卡了一下——你刚说什么来着？", "status_updated": {}}