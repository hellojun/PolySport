"""
邮件服务
发送验证码邮件，SMTP 未配置时降级为日志输出
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.email')


def send_verification_code(to_email: str, code: str):
    """
    发送验证码邮件。
    如果 SMTP 未配置（SMTP_USERNAME 为空），降级为日志打印。
    """
    if not Config.SMTP_USERNAME:
        logger.info(f"[DEV] 验证码 -> {to_email}: {code}")
        return

    subject = "PolySport - 邮箱验证码"
    html = f"""
    <div style="font-family: monospace; max-width: 480px; margin: 0 auto; padding: 32px;">
        <h2 style="color: #000;">PolySport 验证码</h2>
        <p>您的验证码是：</p>
        <div style="font-size: 32px; font-weight: bold; letter-spacing: 8px;
                    color: #FF4500; padding: 16px 0;">{code}</div>
        <p style="color: #666; font-size: 14px;">验证码有效期 5 分钟，请勿分享给他人。</p>
    </div>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    sender_addr = Config.SMTP_SENDER or Config.SMTP_USERNAME
    msg["From"] = formataddr(("PolySport", sender_addr))
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    try:
        if Config.SMTP_USE_TLS:
            server = smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(Config.SMTP_HOST, Config.SMTP_PORT)

        server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
        server.sendmail(msg["From"], [to_email], msg.as_string())
        server.quit()
        logger.info(f"验证码邮件已发送: {to_email}")
    except Exception as e:
        logger.error(f"发送验证码邮件失败: {e}")
        raise
