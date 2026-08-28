"""
Email Service Module for TeleTips Pro
-------------------------------------
Handles sending transactional emails such as account verification and notifications.
Supports standard SMTP with TLS/SSL, branded HTML templates, and fallback logging.
"""

import smtplib
import logging
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from src.utils.config import get_config

logger = logging.getLogger("teletips.email")


def _generate_verification_html(recipient_name: str, verification_url: str, otp_code: str) -> str:
    """Generate branded responsive HTML email template for TeleTips Pro."""
    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>تأكيد حسابك في TeleTips Pro</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #0b0f19;
            color: #e2e8f0;
            margin: 0;
            padding: 0;
            direction: rtl;
        }}
        .container {{
            max-width: 580px;
            margin: 30px auto;
            background: linear-gradient(135deg, #131b2e 0%, #0f172a 100%);
            border: 1px solid #1e293b;
            border-radius: 20px;
            overflow: hidden;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6);
        }}
        .header {{
            background: linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%);
            padding: 30px 20px;
            text-align: center;
        }}
        .logo-title {{
            font-size: 26px;
            font-weight: 900;
            color: #ffffff;
            letter-spacing: -0.5px;
            margin: 0;
        }}
        .logo-badge {{
            display: inline-block;
            background: rgba(255, 255, 255, 0.2);
            font-size: 11px;
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 6px;
            margin-right: 6px;
        }}
        .content {{
            padding: 35px 30px;
            line-height: 1.8;
            text-align: right;
        }}
        .greeting {{
            font-size: 20px;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 12px;
        }}
        .text {{
            font-size: 15px;
            color: #94a3b8;
            margin-bottom: 25px;
        }}
        .otp-box {{
            background: #090d16;
            border: 1px dashed #4f46e5;
            border-radius: 14px;
            padding: 20px;
            text-align: center;
            margin: 25px 0;
        }}
        .otp-label {{
            font-size: 12px;
            color: #818cf8;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }}
        .otp-code {{
            font-size: 36px;
            font-weight: 900;
            color: #38bdf8;
            letter-spacing: 8px;
            font-family: monospace;
            margin: 0;
        }}
        .btn-container {{
            text-align: center;
            margin: 30px 0;
        }}
        .btn {{
            display: inline-block;
            background: linear-gradient(135deg, #4f46e5 0%, #06b6d4 100%);
            color: #ffffff !important;
            text-decoration: none;
            padding: 14px 36px;
            border-radius: 12px;
            font-weight: bold;
            font-size: 16px;
            box-shadow: 0 6px 20px rgba(79, 70, 229, 0.4);
        }}
        .footer {{
            border-top: 1px solid #1e293b;
            padding: 20px 30px;
            text-align: center;
            font-size: 12px;
            color: #64748b;
        }}
        .link-text {{
            color: #38bdf8;
            word-break: break-all;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="logo-title">TeleTips <span class="logo-badge">PRO</span></h1>
            <p style="color: rgba(255, 255, 255, 0.85); font-size: 13px; margin: 6px 0 0 0;">المنصة الذكية لأتمتة وتوجيه قنوات تليجرام</p>
        </div>
        <div class="content">
            <div class="greeting">أهلاً بك، {recipient_name}! 👋</div>
            <p class="text">
                شكراً لانضمامك إلى <strong>TeleTips Pro</strong>. يرجى تأكيد بريدك الإلكتروني لتفعيل حسابك والبدء في إدارة وتوجيه قنواتك بكل سهولة وأمان.
            </p>

            <div class="otp-box">
                <div class="otp-label">رمز التحقق السريع (OTP)</div>
                <div class="otp-code">{otp_code}</div>
            </div>

            <div class="btn-container">
                <a href="{verification_url}" class="btn" target="_blank">⚡ تفعيل الحساب بضغطة واحدة</a>
            </div>

            <p style="font-size: 13px; color: #64748b; text-align: center;">
                صلاحية هذا الرمز والرابط تنتهي خلال <strong>24 ساعة</strong>.
            </p>

            <div style="margin-top: 20px; font-size: 12px; color: #64748b;">
                إذا لم يعمل الزر أعلاه، يمكنك نسخ هذا الرابط وفتحه في المتصفح:<br>
                <a href="{verification_url}" class="link-text">{verification_url}</a>
            </div>
        </div>
        <div class="footer">
            إذا لم تقم بإنشاء هذا الحساب، يمكنك تجاهل هذه الرسالة بأمان.<br>
            © 2026 TeleTips Pro. جميع الحقوق محفوظة.
        </div>
    </div>
</body>
</html>"""


def _generate_verification_text(recipient_name: str, verification_url: str, otp_code: str) -> str:
    """Generate fallback plain text verification message."""
    return f"""أهلاً بك {recipient_name} في TeleTips Pro!

رمز تأكيد حسابك هو: {otp_code}

أو يمكنك تفعيل حسابك مباشرة عبر الضغط على الرابط التالي:
{verification_url}

صلاحية هذا الرمز والرابط تنتهي خلال 24 ساعة.

إذا لم تقم بإنشاء هذا الحساب، يمكنك تجاهل هذه الرسالة.
فريق TeleTips Pro
"""


def send_verification_email_sync(
    recipient_email: str,
    recipient_name: str,
    token: str,
    otp_code: str,
    app_url: str = ""
) -> bool:
    """
    Synchronously send account verification email via SMTP.
    Returns True if sent, False if failed or unconfigured.
    """
    config = get_config()
    smtp_host = config.get("SMTP_HOST", "")
    smtp_port = int(config.get("SMTP_PORT", 587) or 587)
    smtp_user = config.get("SMTP_USER", "")
    smtp_pass = config.get("SMTP_PASSWORD", "")
    smtp_tls = config.get("SMTP_TLS", True)
    smtp_ssl = config.get("SMTP_SSL", False)
    from_email = config.get("SMTP_FROM_EMAIL") or smtp_user or "no-reply@teletips.pro"
    from_name = config.get("SMTP_FROM_NAME", "TeleTips Pro")

    # Base URL for link
    base_url = (app_url or config.get("APP_URL", "")).rstrip("/")
    verification_url = f"{base_url}/verify-email?token={token}" if base_url else f"/verify-email?token={token}"

    logger.info(
        f"🔐 [TeleTips Email Verification] Prepared email for {recipient_email} | OTP: {otp_code} | Link: {verification_url}"
    )

    if not smtp_host:
        logger.info(
            f"ℹ️ SMTP not configured (SMTP_HOST is empty). Verification code logged above: OTP={otp_code}"
        )
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"🔑 تأكيد حسابك في TeleTips Pro - رمز التحقق: {otp_code}"
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = recipient_email

        text_part = MIMEText(_generate_verification_text(recipient_name, verification_url, otp_code), "plain", "utf-8")
        html_part = MIMEText(_generate_verification_html(recipient_name, verification_url, otp_code), "html", "utf-8")

        msg.attach(text_part)
        msg.attach(html_part)

        if smtp_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15) as server:
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
                if smtp_tls:
                    server.starttls()
                if smtp_user and smtp_pass:
                    server.login(smtp_user, smtp_pass)
                server.send_message(msg)

        logger.info(f"✅ Successfully sent verification email to {recipient_email}")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to send verification email to {recipient_email}: {e}")
        return False


def send_verification_email(
    recipient_email: str,
    recipient_name: str,
    token: str,
    otp_code: str,
    app_url: str = ""
):
    """
    Asynchronously dispatch verification email in a background thread
    so that API endpoints return immediately without blocking.
    """
    thread = threading.Thread(
        target=send_verification_email_sync,
        args=(recipient_email, recipient_name, token, otp_code, app_url),
        daemon=True,
    )
    thread.start()
