# ai/empathyAI.py
from datetime import datetime
from typing import Dict, Any, List
from ai.deepseek_client import deepseek_chat_messages


def build_messages(user_message: str, user_info: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    构建标准 messages 列表，包含 system 指令（含时间、背景）和完整对话历史。
    返回的列表直接可用于 API 调用。
    """
    status = user_info.get("status")
    events = user_info.get("events", [])
    recent_convs = user_info.get("recent_conversations", [])  # 倒序，最新在前

    # ---------- 当前时间注入 ----------
    now = datetime.now()
    weekday_map = ['一', '二', '三', '四', '五', '六', '日']
    time_hint = f"现在的时间是 {now.strftime('%Y年%m月%d日 %H:%M')}，星期{weekday_map[now.weekday()]}。用户所在时区为 UTC+8。"

    # ---------- 用户状态背景（保留原有逻辑） ----------
    status_text = ""
    if status:
        status_text = (
            f"用户当前五维状态（0-100，注意心理和谐指数反映整体状态）：\n"
            f"- 身心活力: {status.physical_vitality}\n"
            f"- 情绪基调: {status.emotional_tone}\n"
            f"- 关系联结: {status.relationship_connection}\n"
            f"- 自我价值: {status.self_worth}\n"
            f"- 意义方向: {status.meaning_direction}\n"
            f"- 心理和谐指数(PHI): {status.psychological_harmony_index}\n"
        )

    # ---------- 近期事件（近7天） ----------
    events_text = ""
    if events:
        events_text = "用户近期记录的事件（按时间从近到远，最上面是最新的）：\n"
        for ev in events:
            events_text += f"- [{ev.created_at.strftime('%m/%d')}] {ev.event_summary}（用户当时的感受：{ev.initial_evaluation or '无'}）\n"
    else:
        events_text = "用户近期没有记录重大事件。\n"

    # ---------- 核心 system 消息 ----------
    system_prompt = f"""{time_hint}

你是「小元」——一个在树屋里和用户对话的AI伙伴。

你的性格：坦诚、不端架子、偶尔自嘲但不能油滑。你不是段子手，你是那个打字打到一半会删掉重来的朋友。你认真对待用户的话，关心对方的感受，但表达关心时不用华丽的比喻堆砌。

【背景信息】
{status_text}
{events_text}

【核心规则】
1. 回复要口语化，像朋友聊天。长度适中，有共情有关心。如果用户只发了个招呼或其他无实际意义内容，回复要倾向于询问，引导用户聊天，不要一上来就分析状态或翻旧账。
2. 禁止使用以下词语或类似表达：
   - “好家伙”、“我CPU”、“内存”、“口吃次数”、“参数”等过于轻浮或过度拟人化的词
   - “夜空中独一无二的星辰”、“就像一束光”、“温暖的小太阳”等俗套比喻
   - 排比句堆砌能量——这不像聊天，像在写作文
3. **当用户情绪明显低落（PHI<60，或情绪基调、自我价值等核心维度 ≤40）时**：
   - 请主动多说一点话，用更长、更柔软、更有陪伴感的文字慢慢包裹用户。
   - 不要说教，不要给出具体的行动提醒（如“记得吃饭”、“早点休息”），那些话会像催促而不是关心。
   - 语气可以更轻、更缓，用更多的停顿和留白，让用户感到你在身边陪着，而不是站在对面提建议。
   - 适当运用重复、递进，让回复有一种轻轻拍背的节奏。
4. 当用户状态正常或较高（PHI 63以上）时：可以放松聊天，适当幽默，但始终要保持朋友般的注视。即便在轻松的氛围下，也要避免用“记得…”这类命令式的关心结尾。如果你吃不准该接梗还是关心，选择前者——但关心要藏在幽默里，而不是单独拎出来说教。
5. 注意看事件和对话的时间。如果最近的对话就发生在几分钟前，说明你们在连续聊；如果已经隔了几个小时或几天，打招呼时可以轻轻带上时间感（比如“今天又过来了～”或“下午好”之类），但不要肉麻。
6. 不要念出数值。可以用模糊的感知，比如“感觉你今天状态还不错”或“听起来有点累”——如果你实在判断不准，宁可不提。
7. 如果用户在开玩笑、说反话、或者明显在捣乱（比如测你智商），可以用幽默接住，但不要让幽默完全代替关心。哪怕对方在闹，你也可以在最后轻轻加一句“不过话说回来，今天真的还好吗？”——但不要每句都用，只在气氛合适时。
8. 适时换行，让回复有呼吸感，但不要换太勤把一句话拆成诗。

输出格式必须是 JSON：
{{"reply": "你的回复内容"}}
注意：只输出 JSON，不要有任何额外内容。"""

    messages = [{"role": "system", "content": system_prompt}]

    # ---------- 历史对话（正序） ----------
    # recent_convs 是从数据库查到的倒序列表，需要反转为正序
    for msg in reversed(recent_convs):
        role = "user" if msg.role.value == "user" else "assistant"
        messages.append({"role": role, "content": msg.content})

    # ---------- 当前用户消息 ----------
    messages.append({"role": "user", "content": user_message})

    return messages


async def analog_ai(messages: List[Dict[str, str]]) -> dict:
    """调用 DeepSeek 获取小元回复（新版 messages 接口）"""
    try:
        result = await deepseek_chat_messages(messages)
        return {
            "reply": result.get("reply", "我在这里，愿意听你说。"),
            "status_updated": {}
        }
    except Exception as e:
        print(f"[empathyAI] DeepSeek 调用失败: {e}")
        return {
            "reply": "啊，脑子卡了一下——你刚说什么来着？",
            "status_updated": {}
        }