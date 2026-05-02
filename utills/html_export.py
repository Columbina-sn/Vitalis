# utills/html_export.py
from typing import Dict, Any


def generate_export_html(data: Dict[str, Any]) -> str:
    user = data.get("user", {})
    status = data.get("status")
    snapshots = data.get("snapshots", [])
    anchors = data.get("anchors", [])
    schedules = data.get("schedules", [])
    export_time = data.get("export_time", "现在")

    # 状态条HTML生成函数
    def status_bar(label, value, color):
        safe_value = max(0, min(100, int(value or 0)))
        return f"""
        <div style="margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; font-size: 14px; color: #5a4a3a;">
                <span>{label}</span>
                <span><strong>{safe_value}</strong> / 100</span>
            </div>
            <div style="background: #e8dfc8; height: 8px; border-radius: 10px; margin-top: 4px;">
                <div style="background: {color}; width: {safe_value}%; height: 8px; border-radius: 10px;"></div>
            </div>
        </div>
        """

    status_html = ""
    if status:
        status_html = f"""
        <div style="background: #fffcf0; padding: 20px; border-radius: 24px; margin: 20px 0;">
            <h3 style="color: #b87a48; margin-top: 0;">📊 当前五维状态</h3>
            <p style="color: #a0a0a0; font-size: 12px; margin-bottom: 16px;">最后更新：{status.get('updated', '未知')}</p>
            {status_bar("💪 身心活力", status.get('physical', 50), "#f781be")}
            {status_bar("😊 情绪基调", status.get('emotional', 50), "#f2711c")}
            {status_bar("🤝 关系联结", status.get('relation', 50), "#2a7f78")}
            {status_bar("⭐ 自我价值", status.get('worth', 50), "#f9d342")}
            {status_bar("🧭 意义方向", status.get('meaning', 50), "#4a90e2")}
            {status_bar("☯ 心理和谐", status.get('phi', 50), "#9b59b6")}
        </div>
        """
    else:
        status_html = """
        <div style="background: #fffcf0; padding: 20px; border-radius: 24px; margin: 20px 0; text-align: center; color: #a0a0a0;">
            🍃 状态数据正在采集中，稍后再来看看吧。
        </div>
        """

    # 转义函数
    def escape(s):
        if not s:
            return ""
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    # --- 记忆快照部分 ---
    snapshots_html = ""
    if snapshots:
        items = ""
        for s in snapshots:
            items += f"""
            <div style="background: #fffef5; padding: 12px 16px; border-radius: 20px; margin-bottom: 10px; border-left: 4px solid #a0c4c0;">
                <div style="color: #5a6a5a; font-size: 14px; line-height: 1.5;">{escape(s.get('summary', ''))}</div>
                <div style="color: #b0b0a0; font-size: 12px; margin-top: 6px;">{escape(s.get('created_at', ''))}</div>
            </div>
            """
        snapshots_html = f"""
        <div style="margin: 20px 0;">
            <h3 style="color: #6a7a6a;">📓 小元的日记本（记忆快照）</h3>
            <p style="color: #a0a0a0; font-size: 12px; margin-bottom: 12px;">这些是每天聊天结束后，小元悄悄记下的关于你的点滴。</p>
            {items}
        </div>
        """
    else:
        snapshots_html = '<p style="color: #a0a0a0;">🍃 小元还没来得及写下关于你的日记，多聊聊天吧。</p>'

    # --- 记忆锚点部分 ---
    anchors_html = ""
    if anchors:
        items = ""
        for a in anchors:
            items += f"""
            <div style="background: #fcf9f0; padding: 10px 16px; border-radius: 16px; margin-bottom: 8px; display: flex; align-items: baseline; gap: 8px;">
                <span style="font-size: 12px; background: #e0d5c1; color: #5a4a3a; padding: 2px 10px; border-radius: 20px;">{escape(a.get('type', ''))}</span>
                <span style="color: #4a3a2a;">{escape(a.get('content', ''))}</span>
            </div>
            """
        anchors_html = f"""
        <div style="margin: 20px 0;">
            <h3 style="color: #9a7a5a;">🧷 关于你的小标签（记忆锚点）</h3>
            <p style="color: #a0a0a0; font-size: 12px; margin-bottom: 12px;">小元记住的，关于你的习惯、喜好与重要的人。</p>
            {items}
        </div>
        """
    else:
        anchors_html = '<p style="color: #a0a0a0;">🧷 这里还空空的，小元会慢慢记住更多关于你的事。</p>'

    # --- 用户日程部分 ---
    schedules_html = ""
    if schedules:
        items = ""
        type_map = {
            "short_task": "📋 短期任务",
            "long_goal": "🎯 长期目标",
            "countdown": "⏳ 倒数日",
            "anniversary": "🎉 纪念日",
            "birthday": "🎂 生日"
        }
        for sc in schedules:
            display_type = type_map.get(sc.get('type', ''), f"📌 {sc.get('type', '')}")
            completed_badge = '<span style="font-size: 11px; color: #6a8a6a; margin-left: 8px;">✓ 已完成</span>' if sc.get('is_completed') else ''
            items += f"""
            <div style="background: #fffdf7; padding: 12px 16px; border-radius: 20px; margin-bottom: 10px; border-left: 4px solid #d9b382;">
                <div style="font-weight: bold; color: #7a5a3a;">{escape(sc.get('title', ''))} {completed_badge}</div>
                <div style="color: #a08060; font-size: 13px; margin: 4px 0;">{escape(sc.get('description', '') or '')}</div>
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span style="font-size: 12px; color: #b0a090;">{display_type} · {escape(sc.get('scheduled_time', '未来某天'))}</span>
                </div>
            </div>
            """
        schedules_html = f"""
        <div style="margin: 20px 0;">
            <h3 style="color: #b87a48;">📅 你的日程与念想</h3>
            {items}
        </div>
        """
    else:
        schedules_html = '<p style="color: #a0a0a0;">📅 暂无日程记录，开始规划一些事情吧。</p>'

    # --- 组装完整 HTML ---
    # 转义用户个人信息
    html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>元气岛 · 回忆手帐</title>
    <style>
        body {{
            background: #fefaf0;
            font-family: system-ui, -apple-system, 'Segoe UI', sans-serif;
            line-height: 1.6;
            color: #2c2a24;
            padding: 30px 20px;
            margin: 0;
        }}
        .container {{
            max-width: 700px;
            margin: 0 auto;
            background: #fffef8;
            border-radius: 36px;
            padding: 30px 28px;
            box-shadow: 0 20px 30px rgba(80, 60, 30, 0.08);
            border: 1px solid #f0dfbc;
        }}
        h1 {{
            color: #c9905c;
            border-left: 6px solid #f3c28c;
            padding-left: 18px;
            margin-top: 0;
        }}
        h2 {{
            color: #a57142;
            font-size: 1.3rem;
            margin: 24px 0 12px;
        }}
        .user-card {{
            background: #fcf5e8;
            padding: 18px 22px;
            border-radius: 28px;
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            border: 1px solid #f0dfbc;
        }}
        .user-field {{
            min-width: 180px;
            color: #5a4a3a;
        }}
        .footer {{
            margin-top: 30px;
            text-align: center;
            color: #b0a088;
            font-size: 13px;
            border-top: 1px dashed #e6d0b0;
            padding-top: 20px;
        }}
        body::-webkit-scrollbar {{
            width: 10px;
        }}
        body::-webkit-scrollbar-track {{
            background: #f5ecd8;
            border-radius: 10px;
        }}
        body::-webkit-scrollbar-thumb {{
            background: #ddc8a4;
            border-radius: 10px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🌿 元气岛 · 回忆手帐</h1>
        <p style="color: #b0a088; font-size: 14px; margin-bottom: 24px;">轻轻翻开这一页，时间是 {escape(export_time)}</p>

        <h2>👤 你的信息</h2>
        <div class="user-card">
            <div class="user-field"><strong>手机号</strong><br>{escape(user.get('phone', '未知'))}</div>
            <div class="user-field"><strong>昵称</strong><br>{escape(user.get('nickname', '未知'))}</div>
            <div class="user-field"><strong>邀请码</strong><br>{escape(user.get('invite_code', '未知'))}</div>
            <div class="user-field"><strong>加入元气岛</strong><br>{escape(user.get('created_at', '未知'))}</div>
        </div>

        {status_html}
        {snapshots_html}
        {anchors_html}
        {schedules_html}

        <div class="footer">
            🌱 每一份记忆，都是我们共同走过的路。<br>
            本手帐由 Vitalis 生成，请妥善保管。
        </div>
    </div>
</body>
</html>"""
    return html_template