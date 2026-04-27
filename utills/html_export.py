# utills/html_export.py
from typing import Dict, Any


def generate_export_html(data: Dict[str, Any]) -> str:
    user = data["user"]
    status = data["status"]
    events = data["events"]
    export_time = data["export_time"]

    # 状态条HTML生成函数
    def status_bar(label, value, color):
        return f"""
        <div style="margin-bottom: 12px;">
            <div style="display: flex; justify-content: space-between; font-size: 14px; color: #5a4a3a;">
                <span>{label}</span>
                <span><strong>{value}</strong> / 100</span>
            </div>
            <div style="background: #e8dfc8; height: 8px; border-radius: 10px; margin-top: 4px;">
                <div style="background: {color}; width: {value}%; height: 8px; border-radius: 10px;"></div>
            </div>
        </div>
        """

    status_html = ""
    if status:
        status_html = f"""
        <div style="background: #fffcf0; padding: 20px; border-radius: 24px; margin: 20px 0;">
            <h3 style="color: #b87a48; margin-top: 0;">📊 当前五维状态</h3>
            <p style="color: #a0a0a0; font-size: 12px; margin-bottom: 16px;">最后更新：{status['updated']}</p>
            {status_bar("💪 身心活力", status['physical'], "#f781be")}
            {status_bar("😊 情绪基调", status['emotional'], "#f2711c")}
            {status_bar("🤝 关系联结", status['relation'], "#2a7f78")}
            {status_bar("⭐ 自我价值", status['worth'], "#f9d342")}
            {status_bar("🧭 意义方向", status['meaning'], "#4a90e2")}
            {status_bar("☯ 心理和谐", status['phi'], "#9b59b6")}
        </div>
        """

    events_html = ""
    if events:
        items = ""
        for e in events:
            items += f"""
            <div style="background: #fffef5; padding: 12px 16px; border-radius: 20px; margin-bottom: 10px; border-left: 4px solid #f3c28c;">
                <div style="font-weight: bold; color: #7a5a3a;">{e['summary']}</div>
                <div style="color: #a08060; font-size: 13px; margin: 4px 0;">评价：{e['evaluation']}</div>
                <div style="color: #c0a080; font-size: 12px;">{e['time']}</div>
            </div>
            """
        events_html = f"""
        <div style="margin: 20px 0;">
            <h3 style="color: #b87a48;">📅 重大事件记录（共{len(events)}条）</h3>
            {items}
        </div>
        """
    else:
        events_html = '<p style="color: #a0a0a0;">暂无记录的重大事件</p>'

    # 转义用户输入的内容（防止XSS）
    def escape(s):
        if not s:
            return ""
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    # 注意：在动态插入数据时，要对用户提供的字段进行转义
    html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>元气岛 · 个人数据报告</title>
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
        .badge {{
            background: #f3c28c;
            color: white;
            padding: 4px 12px;
            border-radius: 30px;
            font-size: 12px;
            margin-left: 8px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🌿 元气岛 · 个人数据报告</h1>
        <p style="color: #b0a088; font-size: 14px; margin-bottom: 24px;">导出时间：{export_time}</p>

        <h2>👤 基本信息</h2>
        <div class="user-card">
            <div class="user-field"><strong>手机号</strong><br>{escape(user['phone'])}</div>
            <div class="user-field"><strong>昵称</strong><br>{escape(user['nickname'])}</div>
            <div class="user-field"><strong>邀请码</strong><br>{escape(user['invite_code'])}</div>
            <div class="user-field"><strong>注册时间</strong><br>{user['created_at']}</div>
        </div>

        {status_html}
        {events_html}

        <div class="footer">
            🌱 感谢你在元气岛的每一次记录与对话<br>
            本报告由 Vitalis 自动生成，仅限个人存档使用。
        </div>
    </div>
</body>
</html>"""
    return html_template