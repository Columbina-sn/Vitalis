# utills/email_utils.py
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 587

QQ_EMAIL_FROM = os.getenv("QQ_EMAIL_FROM", "")
QQ_EMAIL_AUTH_CODE = os.getenv("QQ_EMAIL_AUTH_CODE", "")
ADMIN_EMAIL_ALERT_TO = os.getenv("ADMIN_EMAIL_ALERT_TO", "")


def send_admin_login_alert(login_ip: str, login_time: datetime = None) -> bool:
    """
    发送管理员登录提醒邮件
    :param login_ip: 登录请求来源IP
    :param login_time: 登录时间，默认当前时间
    :return: 发送成功返回True，失败返回False
    """
    if not QQ_EMAIL_FROM or not QQ_EMAIL_AUTH_CODE or not ADMIN_EMAIL_ALERT_TO:
        print("[邮件] 缺少邮箱配置，跳过发送")
        return False

    if login_time is None:
        login_time = datetime.now()

    try:
        subject = "【元气岛】管理员登录提醒"
        time_str = login_time.strftime("%Y-%m-%d %H:%M:%S")

        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; background: #faf6ef;">
            <h2 style="color: #b87a48;">🔐 元气岛 · 管理员登录提醒</h2>
            <p style="font-size: 16px;">有设备正在尝试登录管理后台，请确认是否为本人操作。</p>
            <table style="border-collapse: collapse; margin: 20px 0;">
                <tr><td><strong>登录时间</strong></td><td>: {time_str}</td></tr>
                <tr><td><strong>登录IP地址</strong></td><td>: {login_ip}</td></tr>
            </table>
            <p style="color: #d9534f;"><strong>⚠️ 如非本人操作，说明密码已泄露，请立即登录后台熔断管理员入口并修改密码！</strong></p>
            <hr style="border: 1px dashed #e0c48a;">
            <p style="color: #999; font-size: 12px;">本邮件由元气岛系统自动发送，请勿回复。</p>
        </div>
        """

        msg = MIMEMultipart()
        # 修复：使用 formataddr 正确编码发件人显示名
        msg["From"] = formataddr(("元气岛通知", QQ_EMAIL_FROM))
        msg["To"] = ADMIN_EMAIL_ALERT_TO
        msg["Subject"] = Header(subject, "utf-8")
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(QQ_EMAIL_FROM, QQ_EMAIL_AUTH_CODE)
        server.sendmail(QQ_EMAIL_FROM, [ADMIN_EMAIL_ALERT_TO], msg.as_string())
        server.quit()

        print(f"[邮件] 管理员登录提醒已发送至 {ADMIN_EMAIL_ALERT_TO}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        print(f"[邮件] 认证失败，请检查QQ邮箱授权码: {e}")
        return False
    except smtplib.SMTPException as e:
        print(f"[邮件] SMTP协议错误: {e}")
        return False
    except Exception as e:
        print(f"[邮件] 发送失败，其他错误: {e}")
        return False