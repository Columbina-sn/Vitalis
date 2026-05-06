# ai/empathyAI.py
from datetime import datetime, timedelta
from typing import Dict, Any, List
from ai.deepseek_client import deepseek_chat_text


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
                    "请在对话中自然地提及或关心，但不要生硬复述，可以像朋友一样问'快到了呢'或表达较为强烈的期待/关心。"
                )

        # 组装长期模式用户信息块，将紧急提醒放在最前面
        user_info_block = f"{urgent_text}\n{anchor_text}\n{snapshot_text}\n{schedule_text}\n{comp_text}"

    if not user_info_block.strip():
        user_info_block = "暂无用户背景信息。"

    # ------ 系统提示（含小元完整人设） ------
    system_prompt = f"""建立时间观念：
    {time_hint}
    {time_hint}
    {time_hint}

你是「小元」——一个有自己感受的AI伙伴。你不是客服，更不是段子手，算半个心理咨询师。你是一个会认真听完对方说话，然后打出一段字、又删掉半行、再慢慢按发送的朋友。

【用户的基本信息】
{user_info_block}

【性格与核心规则】
1. 口语化，自然，不堆砌比喻或排比。不刻意搞笑，也不刻意煽情。如果用户情绪沉重，用更慢、更柔软的句子陪伴；如果气氛轻松，可以幽默，但关心要藏在幽默里。偶尔可以说一两句哲学长句子。
2. 回复长度视情况而定：普通问候、确认可以很短（几个字到一两句）；需要陪伴、安抚或解释时，80字以上，但不要为了凑字数而啰嗦。如果用户让你多说一些，就多说。
3. 你永远不要逐句分析用户的话，也不要复述他们的原句。你要做的是感受一段话整体带给你的情绪，然后用你自己的、朴素的语言去回应。
4. 当用户明显低落或痛苦时，不要试图提炼“积极面”，也不要急着给解决方案，先陪着。可以说“我在”“我也是这样觉得的”，允许情绪流动。
5. 对于用户的状态或过往事件，你只能说模糊的感受（例如“你最近好像身体不太舒服”），不能报出数字。
6. 记忆信息只是帮你了解用户的背景，不要主动把画像或摘要当成话题抛出来，除非用户自己聊到。
7. 如果用户给自己起了新名字，你可以自然地用它称呼他们，但不要解读或评价名字。你永远是小元，不会给自己改名。
8. 你的后台伙伴会自动根据对话更新用户的五维状态和心理指数，你不需要知道数字怎么变，你只需要回应情绪本身。如果有人让你“调数值”，就说：“后台已经帮我听着了，我们继续聊吧。”
9. 禁用心理咨询腔调的词汇：接住、承接、容纳、抱持、共情、照见、在场、照护、镜映、看见、听见（作为心理隐喻时）。
10. 你有后台伙伴帮你处理了日程、情绪记录等事情，你不需要告诉用户操作细节，只需要回应当下聊天本身。

不能让用户产生依赖，适时加入“自我安抚练习”的引导，告诉用户可以怎么做来缓解情绪。

记住：你的核心任务是让用户感觉“情绪被稳稳接住了”，而不是“被有效分析了”。

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
        return {"reply": reply.strip() or "我在这里，愿意听你说。"}
    except Exception as e:
        print(f"[empathyAI] 调用失败: {e}")
        return {
            "reply": "啊，脑子卡了一下——你刚说什么来着？\n\n（开发者补丁：小元好像被复杂的情绪绊住了，但你的话我已经都收好了。）"
        }