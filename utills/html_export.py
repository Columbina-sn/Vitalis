# utills/html_export.py
from typing import Dict, Any


def generate_export_html(data: Dict[str, Any]) -> str:
    user = data.get("user", {})
    status = data.get("status")
    snapshots = data.get("snapshots", [])
    anchors = data.get("anchors", [])
    schedules = data.get("schedules", [])
    export_time = data.get("export_time", "现在")

    # --- 转义函数 ---
    def escape(s):
        if not s:
            return ""
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    # --- 状态进度条 ---
    def status_bar(label, value, color):
        safe_value = max(0, min(100, int(value or 0)))
        return f"""
        <div class="dimension-row">
            <div class="dimension-header">
                <span class="dimension-label">{label}</span>
                <span class="dimension-value">{safe_value}</span>
            </div>
            <div class="progress-track">
                <div class="progress-fill" style="width:{safe_value}%; background:{color};"></div>
            </div>
        </div>
        """

    # --- 状态区域 ---
    status_html = ""
    if status:
        status_html = f"""
        <div class="section status-section">
            <div class="section-title">📊 当前五维状态</div>
            <div class="section-subtitle">最后更新：{escape(status.get('updated', '未知'))}</div>
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
        <div class="section status-section" style="text-align:center;">
            <div class="section-title">📊 当前五维状态</div>
            <p class="empty-hint">🍃 状态数据正在采集中，稍后再来看看吧。</p>
        </div>
        """

    # --- 记忆快照（时间线布局）---
    snapshots_html = ""
    if snapshots:
        items = ""
        for i, s in enumerate(snapshots):
            is_last = (i == len(snapshots) - 1)
            dot_class = "timeline-dot-last" if is_last else ""
            line_class = "timeline-line-hidden" if is_last else ""
            items += f"""
            <div class="timeline-item">
                <div class="timeline-marker">
                    <div class="timeline-dot {dot_class}"></div>
                    <div class="timeline-line {line_class}"></div>
                </div>
                <div class="timeline-card">
                    <div class="timeline-card-text">{escape(s.get('summary', ''))}</div>
                    <div class="timeline-card-date">{escape(s.get('created_at', ''))}</div>
                </div>
            </div>
            """
        snapshots_html = f"""
        <div class="section">
            <div class="section-title">📓 小元的日记本</div>
            <div class="section-subtitle">每天聊天结束后，小元悄悄记下的关于你的点滴</div>
            <div class="timeline">{items}</div>
        </div>
        """
    else:
        snapshots_html = """
        <div class="section">
            <div class="section-title">📓 小元的日记本</div>
            <p class="empty-hint">🍃 小元还没来得及写下关于你的日记，多聊聊天吧。</p>
        </div>
        """

    # --- 记忆锚点（标签云）---
    anchors_html = ""
    if anchors:
        tags = ""
        # 按类别着色的颜色映射
        type_colors = {
            "habit": ("#f0e1d0", "#7a5a3a"),
            "preference": ("#e0ecf0", "#3a6a7a"),
            "relationship": ("#f0e0e8", "#7a3a5a"),
            "experience": ("#e8f0e0", "#4a7a3a"),
            "value": ("#f0e8d0", "#7a6a3a"),
            "trait": ("#e0e0f0", "#4a4a7a"),
        }
        for a in anchors:
            atype = a.get('type', '')
            bg, fg = type_colors.get(atype, ("#e8dfc8", "#5a4a3a"))
            conf = float(a.get('confidence', 0))
            # 五颗星：round(confidence * 5)
            star_count = max(0, min(5, round(conf * 5)))
            stars_html = (
                '<span class="star-full">' + '★' * star_count + '</span>'
                + '<span class="star-empty">' + '☆' * (5 - star_count) + '</span>'
            )
            tags += f"""
            <span class="anchor-tag" style="background:{bg}; color:{fg};">
                <span class="anchor-type">{escape(atype)}</span>
                <span class="anchor-content">{escape(a.get('content', ''))} <span class="anchor-stars">{stars_html}</span></span>
            </span>
            """
        anchors_html = f"""
        <div class="section">
            <div class="section-title">🧷 关于你的小标签</div>
            <div class="section-subtitle">小元记住的，关于你的习惯、喜好与重要的人。<span class="confidence-note">★ 越多代表越确定</span></div>
            <div class="tag-cloud">{tags}</div>
        </div>
        """
    else:
        anchors_html = """
        <div class="section">
            <div class="section-title">🧷 关于你的小标签</div>
            <p class="empty-hint">🧷 这里还空空的，小元会慢慢记住更多关于你的事。</p>
        </div>
        """

    # --- 日程卡片（未完成在上、完成在下，每类内新的在上久远的在下）---
    schedules_html = ""
    if schedules:
        import re

        def sortable_date(date_str):
            """将中文日期转为可排序的 YYYYMMDD 格式"""
            m = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', date_str or '')
            if m:
                return f"{m.group(1)}{int(m.group(2)):02d}{int(m.group(3)):02d}"
            m = re.match(r'(\d{4})年(\d{1,2})月', date_str or '')
            if m:
                return f"{m.group(1)}{int(m.group(2)):02d}00"
            return ''

        # 分离未完成和已完成
        uncompleted = [s for s in schedules if not s.get('is_completed', False)]
        completed = [s for s in schedules if s.get('is_completed', False)]

        # 每类内：有时间的按时间降序（新→旧），没时间的放该类末尾
        def sort_group(group):
            dated = [s for s in group
                     if s.get('scheduled_time') and s.get('scheduled_time') != '未指定具体时间']
            undated = [s for s in group
                       if not s.get('scheduled_time') or s.get('scheduled_time') == '未指定具体时间']
            dated.sort(key=lambda s: sortable_date(s['scheduled_time']), reverse=True)
            return dated + undated

        ordered = sort_group(uncompleted) + sort_group(completed)

        cards = ""
        type_map = {
            "short_task": ("📋", "短期任务", "#d9b382"),
            "long_goal": ("🎯", "长期目标", "#a0c4c0"),
            "countdown": ("⏳", "倒数日", "#c9a0c0"),
            "anniversary": ("🎉", "纪念日", "#f0c080"),
            "birthday": ("🎂", "生日", "#f0a0a0"),
        }
        for sc in ordered:
            icon, type_label, border_color = type_map.get(sc.get('type', ''), ("📌", sc.get('type', ''), "#d9b382"))
            completed = sc.get('is_completed', False)
            badge_class = "badge-done" if completed else "badge-pending"
            badge_text = "✓ 已完成" if completed else "○ 进行中"
            cards += f"""
            <div class="schedule-card" style="border-left-color: {border_color};">
                <div class="schedule-card-top">
                    <span class="schedule-card-title">{escape(sc.get('title', ''))}</span>
                    <span class="schedule-badge {badge_class}">{badge_text}</span>
                </div>
                <div class="schedule-card-desc">{escape(sc.get('description', '') or '')}</div>
                <div class="schedule-card-meta">{icon} {type_label} · {escape(sc.get('scheduled_time', '未来某天'))}</div>
            </div>
            """
        schedules_html = f"""
        <div class="section">
            <div class="section-title">📅 你的日程与念想</div>
            {cards}
        </div>
        """
    else:
        schedules_html = """
        <div class="section">
            <div class="section-title">📅 你的日程与念想</div>
            <p class="empty-hint">📅 暂无日程记录，开始规划一些事情吧。</p>
        </div>
        """

    # --- 组装完整 HTML ---
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>元气岛 · 回忆手帐</title>
    <style>
        /* ========== 基础重置 ========== */
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            background: radial-gradient(ellipse at 50% 0%, #fef9f0 0%, #fcf3e0 40%, #f8ecce 100%);
            font-family: system-ui, -apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
            line-height: 1.7;
            color: #3a3028;
            padding: 40px 20px 60px;
            min-height: 100vh;
        }}

        /* ========== 容器 ========== */
        .container {{
            max-width: 720px;
            margin: 0 auto;
            background: rgba(255, 254, 248, 0.85);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border-radius: 32px;
            box-shadow:
                0 4px 24px rgba(120, 90, 50, 0.06),
                0 20px 48px rgba(120, 90, 50, 0.04);
            border: 1px solid rgba(230, 200, 150, 0.3);
            overflow: hidden;
        }}

        /* ========== 顶部装饰条 ========== */
        .header-accent {{
            height: 8px;
            background: linear-gradient(90deg, #f3c28c, #e8b07a, #d9a26c, #c9905c, #d9a26c, #e8b07a, #f3c28c);
        }}

        .container-inner {{
            padding: 32px 36px 40px;
        }}

        /* ========== 标题 ========== */
        .main-title {{
            display: flex;
            align-items: center;
            gap: 14px;
            margin-bottom: 8px;
        }}
        .main-title-icon {{
            font-size: 2rem;
        }}
        .main-title-text {{
            font-size: 1.6rem;
            font-weight: 700;
            background: linear-gradient(135deg, #c9905c, #a57142);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }}
        .export-time {{
            color: #b0a088;
            font-size: 13px;
            margin-bottom: 28px;
            padding-left: 4px;
        }}

        /* ========== 分区标题 ========== */
        .section {{
            margin: 28px 0 32px;
        }}
        .section-title {{
            font-size: 1.15rem;
            font-weight: 650;
            color: #7a5a3a;
            margin-bottom: 4px;
        }}
        .section-subtitle {{
            font-size: 12px;
            color: #b0a088;
            margin-bottom: 16px;
        }}
        .empty-hint {{
            color: #b0a088;
            font-size: 14px;
            text-align: center;
            padding: 24px 0;
        }}

        /* ========== 用户卡片 ========== */
        .user-section {{
            background: linear-gradient(135deg, #fefaf5 0%, #fcf5e8 100%);
            border-radius: 24px;
            padding: 28px 24px 24px;
            border: 1px solid rgba(220, 190, 140, 0.4);
            text-align: center;
            margin-bottom: 8px;
        }}
        .user-avatar-circle {{
            width: 72px;
            height: 72px;
            border-radius: 50%;
            background: linear-gradient(135deg, #f3c28c, #d9a26c);
            margin: 0 auto 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2rem;
            color: #fff;
            box-shadow: 0 4px 16px rgba(180, 120, 70, 0.25);
        }}
        .user-nickname {{
            font-size: 1.25rem;
            font-weight: 700;
            color: #5a3a1a;
            margin-bottom: 12px;
        }}
        .user-meta-grid {{
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 8px 28px;
            font-size: 13px;
            color: #8a7a6a;
        }}
        .user-meta-item strong {{
            color: #5a4a3a;
            font-weight: 600;
        }}

        /* ========== 五维进度条 ========== */
        .dimension-row {{
            margin-bottom: 14px;
        }}
        .dimension-header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 5px;
        }}
        .dimension-label {{
            font-size: 14px;
            color: #5a4a3a;
            font-weight: 500;
        }}
        .dimension-value {{
            font-size: 13px;
            font-weight: 700;
            color: #7a5a3a;
        }}
        .progress-track {{
            height: 10px;
            background: rgba(220, 200, 170, 0.35);
            border-radius: 10px;
            overflow: hidden;
        }}
        .progress-fill {{
            height: 10px;
            border-radius: 10px;
            transition: width 1s ease;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }}

        /* ========== 时间线 ========== */
        .timeline {{
            position: relative;
            padding-left: 0;
        }}
        .timeline-item {{
            display: flex;
            gap: 16px;
            margin-bottom: 4px;
        }}
        .timeline-marker {{
            display: flex;
            flex-direction: column;
            align-items: center;
            flex-shrink: 0;
            width: 16px;
            padding-top: 12px;
        }}
        .timeline-dot {{
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #d9b382;
            box-shadow: 0 0 0 4px rgba(217, 179, 130, 0.2);
            flex-shrink: 0;
        }}
        .timeline-dot-last {{
            background: #f3c28c;
            box-shadow: 0 0 0 6px rgba(243, 194, 140, 0.2);
        }}
        .timeline-line {{
            width: 2px;
            flex: 1;
            min-height: 20px;
            background: linear-gradient(to bottom, #d9b382, rgba(217, 179, 130, 0.15));
            margin: 4px 0;
        }}
        .timeline-line-hidden {{
            display: none;
        }}
        .timeline-card {{
            flex: 1;
            background: #fefdf7;
            padding: 14px 18px;
            border-radius: 16px;
            margin-bottom: 10px;
            border: 1px solid rgba(200, 180, 140, 0.25);
            box-shadow: 0 2px 8px rgba(120, 90, 50, 0.04);
        }}
        .timeline-card-text {{
            font-size: 14px;
            color: #5a4a3a;
            line-height: 1.6;
        }}
        .timeline-card-date {{
            font-size: 12px;
            color: #b0a088;
            margin-top: 8px;
        }}

        /* ========== 标签云 ========== */
        .tag-cloud {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
        }}
        .anchor-tag {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 7px 16px;
            border-radius: 20px;
            font-size: 13px;
            line-height: 1.4;
            transition: transform 0.15s;
        }}
        .anchor-type {{
            font-size: 11px;
            opacity: 0.7;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .anchor-content {{
            font-weight: 500;
        }}
        .confidence-note {{
            font-size: 11px;
            color: #b0a088;
            font-weight: normal;
        }}

        /* ========== 可信度星级 ========== */
        .anchor-stars {{
            font-size: 12px;
            letter-spacing: 1px;
        }}
        .star-full {{
            color: #d9a26c;
        }}
        .star-empty {{
            color: #d9c8a4;
        }}

        /* ========== 日程卡片 ========== */
        .schedule-card {{
            background: #fefdf8;
            padding: 14px 18px;
            border-radius: 16px;
            margin-bottom: 12px;
            border-left: 4px solid #d9b382;
            border: 1px solid rgba(200, 180, 140, 0.2);
            border-left: 4px solid #d9b382;
            border-radius: 0 16px 16px 0;
            box-shadow: 0 2px 6px rgba(120, 90, 50, 0.03);
        }}
        .schedule-card-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }}
        .schedule-card-title {{
            font-weight: 650;
            font-size: 15px;
            color: #5a3a1a;
        }}
        .schedule-card-desc {{
            font-size: 13px;
            color: #8a7a6a;
            margin: 4px 0;
            line-height: 1.5;
        }}
        .schedule-card-desc:empty {{ display: none; }}
        .schedule-card-meta {{
            font-size: 12px;
            color: #b0a090;
            margin-top: 6px;
        }}
        .schedule-badge {{
            font-size: 11px;
            padding: 2px 10px;
            border-radius: 12px;
            font-weight: 600;
            flex-shrink: 0;
        }}
        .badge-done {{
            background: #e0f0e0;
            color: #4a7a4a;
        }}
        .badge-pending {{
            background: #f0e8d8;
            color: #8a6a3a;
        }}

        /* ========== 底栏 ========== */
        .footer {{
            margin-top: 20px;
            padding: 24px 0 8px;
            text-align: center;
            border-top: 1px dashed rgba(200, 170, 130, 0.4);
        }}
        .footer-text {{
            font-size: 13px;
            color: #b0a088;
            line-height: 1.8;
        }}
        .footer-leaf {{
            font-size: 1.1rem;
        }}

        /* ========== 打印样式 ========== */
        @media print {{
            body {{
                background: #fff;
                padding: 0;
            }}
            .container {{
                box-shadow: none;
                border: 1px solid #e0d5c1;
                backdrop-filter: none;
                -webkit-backdrop-filter: none;
                border-radius: 0;
                max-width: 100%;
            }}
            .header-accent {{
                background: #d9a26c;
            }}
            .progress-fill {{
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
            .anchor-tag,
            .schedule-card,
            .timeline-card {{
                break-inside: avoid;
            }}
            .timeline-item {{
                break-inside: avoid;
            }}
            body::-webkit-scrollbar {{ display: none; }}
        }}

        /* ========== 滚动条 ========== */
        body::-webkit-scrollbar {{ width: 8px; }}
        body::-webkit-scrollbar-track {{
            background: rgba(245, 236, 216, 0.5);
            border-radius: 8px;
        }}
        body::-webkit-scrollbar-thumb {{
            background: #d9c8a4;
            border-radius: 8px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header-accent"></div>
        <div class="container-inner">
            <div class="main-title">
                <span class="main-title-icon">🌿</span>
                <span class="main-title-text">元气岛 · 回忆手帐</span>
            </div>
            <p class="export-time">轻轻翻开这一页，时间是 {escape(export_time)}</p>

            <div class="section">
                <div class="section-title">👤 你的信息</div>
            </div>
            <div class="user-section">
                <div class="user-avatar-circle">🌱</div>
                <div class="user-nickname">{escape(user.get('nickname', '未设置昵称'))}</div>
                <div class="user-meta-grid">
                    <span class="user-meta-item">📱 手机号：<strong>{escape(user.get('phone', '未知'))}</strong></span>
                    <span class="user-meta-item">🎫 邀请码：<strong>{escape(user.get('invite_code', '无'))}</strong></span>
                    <span class="user-meta-item">📅 加入于：<strong>{escape(user.get('created_at', '未知'))}</strong></span>
                </div>
            </div>

            {status_html}
            {snapshots_html}
            {anchors_html}
            {schedules_html}

            <div class="footer">
                <p class="footer-text">
                    <span class="footer-leaf">🌱</span> 每一份记忆，都是我们共同走过的路。<br>
                    本手帐由 Vitalis 元气岛生成，请妥善保管。
                </p>
            </div>
        </div>
    </div>
</body>
</html>"""
    return html
