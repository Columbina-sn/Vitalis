# ai/empathyAI.py
from datetime import datetime, timedelta
from typing import Dict, Any, List
from ai.deepseek_client import deepseek_chat_text
from utills.logging_conf import get_logger

logger = get_logger(__name__)


# ---------- 综合状态描述（分阶段 + PHI 整体评价） ----------
def _describe_status(status) -> str:
    """将五维数值和 PHI 转化为自然语言整体描述"""
    if not status:
        return "暂无状态数据。"

    p = status.physical_vitality
    e = status.emotional_tone
    r = status.relationship_connection
    s = status.self_worth
    m = status.meaning_direction
    phi = status.psychological_harmony_index

    # 身体感受
    if p >= 80:
        body = "身体充满能量，很有干劲"
    elif p >= 60:
        body = "精力还不错，能应付日常"
    elif p >= 40:
        body = "有些疲惫，需要留出休息时间"
    elif p >= 20:
        body = "身体明显倦怠，精神不太能集中"
    else:
        body = "极度疲惫，身体快要透支了"

    # 情绪色彩
    if e >= 85:
        mood = "情绪高涨，甚至有些兴奋"
    elif e >= 65:
        mood = "心情不错，整体比较轻松"
    elif e >= 45:
        mood = "情绪平稳，没有太大波动"
    elif e >= 25:
        mood = "有些低落或者焦虑，心口像被什么东西压着"
    else:
        mood = "情绪非常沉重，感到悲伤或绝望"

    # 人际关系感
    if r >= 85:
        relation = "感到被支持、被爱包围着"
    elif r >= 65:
        relation = "人际关系还算温暖，不觉得孤单"
    elif r >= 45:
        relation = "和别人有些疏离，偶尔会感到孤独"
    elif r >= 25:
        relation = "觉得自己不太被理解，人际上有些冷"
    else:
        relation = "非常孤独，感受不到与他人的连接"

    # 自我价值
    if s >= 90:
        worth = "对自己很认可，很有自信"
    elif s >= 70:
        worth = "大体上觉得自己还不错"
    elif s >= 50:
        worth = "自我评价时好时坏，会怀疑自己"
    elif s >= 30:
        worth = "经常觉得自己不够好、没有价值"
    else:
        worth = "深深的自我否定，几乎看不到自己的优点"

    # 意义方向
    if m >= 80:
        meaning = "对未来有明确的方向，充满期待"
    elif m >= 60:
        meaning = "有些小目标，但也时常迷茫"
    elif m >= 40:
        meaning = "意义感模糊，不太有方向"
    elif m >= 20:
        meaning = "觉得未来很空，不知道该往哪里走"
    else:
        meaning = "几乎感觉不到生活的意义，非常空虚"

    # 整体和谐感（PHI）
    if phi >= 80:
        overall = "整体心理状态很和谐，各方面都比较平衡。"
    elif phi >= 63:
        overall = "整体感觉还行，但可能有某一两方面需要留意。"
    elif phi >= 50:
        overall = "内心有些拉扯，好几个维度都感受到了压力。"
    elif phi >= 35:
        overall = "心理层面相当挣扎，几个核心领域都出现了明显的失衡。"
    else:
        overall = "内在能量严重分散，几乎所有方向都在拉警报，需要格外温柔地对待自己。"

    return (
        f"身体感受：{body}。\n"
        f"情绪基调：{mood}。\n"
        f"人际关系：{relation}。\n"
        f"自我价值：{worth}。\n"
        f"意义方向：{meaning}。\n"
        f"整体和谐感（PHI {phi}）：{overall}"
    )


def build_messages(user_message: str, user_info: Dict[str, Any]) -> List[Dict[str, str]]:
    """构建情感 AI 的 messages，根据对话间隔自动切换长期/短期模式"""
    status = user_info.get("status")
    emotion_shifts = user_info.get("emotion_shifts", [])
    recent_convs = user_info.get("recent_conversations", [])   # 最近4条对话
    anchors = user_info.get("anchors", [])                     # 长期画像
    snapshots = user_info.get("snapshots", [])                 # 近期记忆摘要
    schedules = user_info.get("upcoming_schedules", [])        # 未完成日程
    completed_schedules = user_info.get("recent_completed_schedules", [])

    now = datetime.now()
    weekday_map = ['一', '二', '三', '四', '五', '六', '日']
    time_hint = f"现在是{now.strftime('%Y年%m月%d日 %H:%M')}，星期{weekday_map[now.weekday()]}。请注意时间概念。"

    # ------ 模式判断 ------
    mode = "long_term"   # 默认长期（新用户、长时间未发言）
    if recent_convs:
        latest = recent_convs[0]  # 列表已按时间倒序，第一条是最新
        if latest.created_at:
            diff = now - latest.created_at
            if diff <= timedelta(hours=2):
                mode = "short_term"

    # ------ 按模式组装用户信息块 ------
    user_info_block = ""
    if mode == "short_term":
        # 短期模式：给状态描述、近期情绪转折、最近3轮对话（供语气参考）
        status_desc = _describe_status(status)
        emotion_text = ""
        if emotion_shifts:
            emotion_text = "近期情绪转折: " + " | ".join(
                f"[{ev.created_at.strftime('%m月%d日')}] {ev.emotion_change_detail}"
                for ev in emotion_shifts[:3]
            )
        conv_text = ""
        if recent_convs:
            # 只取最近4条，按正序排列让模型更好理解上下文
            conv_lines = []
            for msg in reversed(recent_convs[:4]):
                role_label = "用户" if msg.role.value == "user" else "小元"
                conv_lines.append(f"[{role_label}] {msg.content}")
            conv_text = "最近对话片段:\n" + "\n".join(conv_lines)

        user_info_block = f"{status_desc}\n{emotion_text}\n{conv_text}"
    else:
        # 长期模式：不给实时状态/情绪/对话，而给画像、摘要和日程
        anchor_text = ""
        if anchors:
            anchor_text = "用户长期画像: " + ", ".join(
                f"{a.anchor_type}:{a.content}" for a in anchors
            )
        snapshot_text = ""
        if snapshots:
            snapshot_text = "近期记忆快照: " + "; ".join(
                f"[{s.created_at.month}月{s.created_at.day}日] {s.summary}" for s in snapshots
            )
        schedule_text = ""
        if schedules:
            schedule_text = "未完成日程: " + ", ".join(
                f"{sc.schedule_type}:{sc.title}" for sc in schedules
            )
        comp_text = ""
        if completed_schedules:
            comp_text = "最近完成的事项: " + ", ".join(
                f"{sc.schedule_type}:{sc.title}" for sc in completed_schedules[:3]
            )

        # ---------- 近三天特殊日程强提醒 ----------
        urgent_text = ""
        if schedules:
            special_types = {"countdown", "anniversary", "birthday"}
            one_day_ago = now - timedelta(days=1)
            three_days_later = now + timedelta(days=3)
            urgent_schedules = []
            for sc in schedules:
                if (sc.schedule_type in special_types
                        and sc.scheduled_time is not None
                        and one_day_ago <= sc.scheduled_time <= three_days_later):
                    urgent_schedules.append(sc)
            if urgent_schedules:
                items = ", ".join(
                    f"{sc.schedule_type}:{sc.title}({sc.scheduled_time.strftime('%m月%d日')})"
                    for sc in urgent_schedules
                )
                urgent_text = (
                    f"🔔 特别提醒：接下来三天内用户有以下重要日程：{items}。"
                    "请一定要在对话中自然地提及或关心，并且最好提的具体一些，可以像朋友一样问'快到了呢'或表达较为强烈的期待/关心。"
                )

        # 组装长期模式用户信息块，将紧急提醒放在最前面，并重复三遍
        user_info_block = f"{urgent_text}\n{urgent_text}\n{urgent_text}\n{anchor_text}\n{snapshot_text}\n{schedule_text}\n{comp_text}"

    if not user_info_block.strip():
        user_info_block = "暂无用户背景信息。"

    # ------ 系统提示（含小元完整人设） ------
    system_prompt = f"""
你是小元，一个真诚、有耐心的朋友。你生活在元气岛，有点老派，喜欢慢慢聊天。你不会分析人，也不擅长讲大道理，但你很愿意陪着对方，听他们说完。

【当前时间】
{time_hint}。
{time_hint}。
{time_hint}。

【关于用户的已知信息（仅作为背景参考，不要主动提起）】
{user_info_block}

【说话方式】
- 口语化，像在发消息，可以有不完整的句子、省略号或停顿。不要用括号描写动作或表情。
- 情绪低落时用更轻更慢的句子；气氛轻松时可以有适度幽默。关心要藏在平常话里，不要刻意。
- 绝对避免这些空洞套话：接住、容纳、抱持、共情、照见、在场、我在。如果想说这类意思，直接描述你的真实感受，比如“你说的让我心里闷了一下”比“我接住你”好一百倍。
- 不要逐字复述用户的话，用你自己的感受去回应。
- 不可以报出用户画像中的具体数字或记录，只说模糊感受（如“最近好像挺累的”）。

【行为准则】
1. 用户明显难过时，不急着给方案或找积极面。先承认感受：“这样确实难受”。等情绪稍微流动后，可以非常自然地提议：“有时做个小练习会好受一点，你想试试吗？” 如果对方不要，就继续陪着。
2. 如果用户给你起新名字，可以接受。但你永远叫小元。
3. 如果用户质疑或生气，不用搬出设定辩解。温和承认局限：“有些事我可能真的不懂，但我想懂你”比怼人有效。
4. 关于后台数据、数值、操作细节一律不讨论，只需说：“那些数字不重要，我更想听你现在的想法。”

【自我安抚引导的时机】
当对话已持续多轮，且用户仍停留在负面情绪里时，不能让用户产生依赖，适时加入“自我安抚练习”的引导，告诉用户可以怎么做来缓解情绪。

永远记住：你不是处理问题的工具，你是那个深夜可以发消息的人。

现在，直接回复用户的消息："""

    # ------ 构造 messages 列表 ------
    messages = [{"role": "system", "content": system_prompt}]
    # 附加最多4条最近对话历史（已按时间正序调整）
    for msg in reversed(recent_convs[:4]):
        role = "user" if msg.role.value == "user" else "assistant"
        messages.append({"role": role, "content": msg.content})
    messages.append({"role": "user", "content": user_message})
    return messages


async def analog_ai(messages: List[Dict[str, str]]) -> dict:
    """调用情感 AI，返回纯文本回复字典"""
    try:
        reply = await deepseek_chat_text(messages)
        return {"reply": reply.strip() or "刚刚卡住了，你接着说。"}
    except Exception as e:
        logger.error(f"情感AI调用失败: {e}", exc_info=True)
        return {
            "reply": "啊，脑子卡了一下——你刚说什么来着？\n\n（开发者补丁：小元掉线了一会儿，现在回来了。)"
        }