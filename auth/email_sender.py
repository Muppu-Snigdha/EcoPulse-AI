

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum

from dotenv import load_dotenv

load_dotenv()


class SendResult(Enum):
    """
    Typed result for send_otp_email() so callers can distinguish
    the failure mode without exposing credentials or raw exceptions.
    """
    OK = "ok"
    AUTH_FAILURE = "auth_failure"   # 535 — App Password rejected by Gmail
    NETWORK_FAILURE = "network_failure"  # Could not reach server
    NOT_CONFIGURED = "not_configured"    # SMTP env vars missing
    UNKNOWN_FAILURE = "unknown_failure"  # Any other error


def _get_smtp_config() -> dict | None:
    """
    Read SMTP credentials from environment variables.
    Returns None if any required variable is missing.

    Note: SMTP_PASSWORD has all whitespace removed before use.
    Google App Passwords are displayed in groups (e.g. "xxxx xxxx xxxx xxxx")
    but the SMTP server expects the 16-character form with no spaces.
    """
    host = os.getenv("SMTP_HOST", "").strip()
    port_str = os.getenv("SMTP_PORT", "587").strip()
    user = os.getenv("SMTP_USER", "").strip()
    # Remove ALL whitespace from the App Password — Google displays it in
    # 4-character groups separated by spaces, but SMTP login requires the
    # raw 16-character string with no spaces.
    password = "".join(os.getenv("SMTP_PASSWORD", "").split())
    sender = os.getenv("SMTP_FROM", user).strip() or user

    if not host or not user or not password:
        return None

    try:
        port = int(port_str)
    except ValueError:
        port = 587

    return {"host": host, "port": port, "user": user,
            "password": password, "sender": sender}


def send_otp_email(to_email: str, otp_code: str, full_name: str = "") -> SendResult:
    """
    Send a password-reset OTP email.

    Parameters
    ----------
    to_email  : str  Recipient email address.
    otp_code  : str  6-digit OTP (passed in — not generated here).
    full_name : str  Optional recipient name for personalisation.

    Returns
    -------
    SendResult enum value:
      SendResult.OK              — email sent successfully
      SendResult.NOT_CONFIGURED  — SMTP env vars missing
      SendResult.AUTH_FAILURE    — credentials rejected by Gmail (535)
      SendResult.NETWORK_FAILURE — could not connect to SMTP server
      SendResult.UNKNOWN_FAILURE — any other error

    Never raises — all exceptions are caught.
    The caller is responsible for showing a user-facing error.
    """
    cfg = _get_smtp_config()
    if cfg is None:
        return SendResult.NOT_CONFIGURED

    greeting = f"Hi {full_name}," if full_name else "Hello,"

    subject = "EcoPulse AI — Your Password Reset OTP"
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {{ font-family: -apple-system, 'Segoe UI', sans-serif; background: #0a0f1e; margin: 0; padding: 20px; }}
    .container {{ max-width: 480px; margin: 0 auto; background: #111827;
                  border-radius: 12px; border: 1px solid #1f2d3d; overflow: hidden; }}
    .header {{ background: linear-gradient(135deg, #064e3b, #10b981);
               padding: 24px 32px; text-align: center; }}
    .header h1 {{ color: #fff; margin: 0; font-size: 22px; font-weight: 700; letter-spacing: 0.5px; }}
    .header p {{ color: rgba(255,255,255,0.8); margin: 4px 0 0; font-size: 13px; }}
    .body {{ padding: 32px; color: #e2e8f0; }}
    .body p {{ margin: 0 0 16px; font-size: 15px; line-height: 1.6; color: #cbd5e1; }}
    .otp-box {{ background: #0a0f1e; border: 2px solid #10b981; border-radius: 12px;
                padding: 20px; text-align: center; margin: 24px 0; }}
    .otp-code {{ font-size: 36px; font-weight: 800; letter-spacing: 10px;
                  color: #10b981; font-family: monospace; }}
    .expiry {{ font-size: 12px; color: #94a3b8; margin-top: 8px; }}
    .footer {{ padding: 20px 32px; border-top: 1px solid #1f2d3d;
               font-size: 12px; color: #64748b; text-align: center; }}
    .warning {{ background: rgba(239,68,68,0.08); border: 1px solid rgba(239,68,68,0.3);
                border-radius: 8px; padding: 12px 16px; margin-top: 16px;
                font-size: 13px; color: #fca5a5; }}
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>⚡ EcoPulse AI</h1>
      <p>Intelligent Energy. Sustainable Future.</p>
    </div>
    <div class="body">
      <p>{greeting}</p>
      <p>You requested a password reset for your EcoPulse AI account. Use the OTP below to proceed:</p>
      <div class="otp-box">
        <div class="otp-code">{otp_code}</div>
        <div class="expiry">This OTP expires in <strong>5 minutes</strong></div>
      </div>
      <p>Enter this code on the password reset screen. Once used, the code becomes invalid.</p>
      <div class="warning">
        🔒 If you did not request this, please ignore this email. Your account remains secure.
      </div>
    </div>
    <div class="footer">
      EcoPulse AI · Local Energy Intelligence Platform<br>
      This is an automated message — please do not reply.
    </div>
  </div>
</body>
</html>
"""
    text_body = (
        f"{greeting}\n\n"
        f"Your EcoPulse AI password reset OTP is: {otp_code}\n\n"
        f"This OTP expires in 5 minutes.\n\n"
        f"If you did not request this, ignore this email."
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["sender"]
    msg["To"] = to_email
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["sender"], [to_email], msg.as_string())
        return SendResult.OK
    except smtplib.SMTPAuthenticationError:
        # 535 — App Password rejected by Gmail.
        # Most common causes: spaces left in the password (now fixed),
        # password generated for a different account, or 2FA was reset.
        # Do NOT expose credentials.
        return SendResult.AUTH_FAILURE
    except (smtplib.SMTPConnectError, ConnectionRefusedError, OSError):
        # Could not reach the SMTP server
        return SendResult.NETWORK_FAILURE
    except Exception:
        # Any other SMTP / network failure — credentials stay private
        return SendResult.UNKNOWN_FAILURE


def is_smtp_configured() -> bool:
    """Return True if all required SMTP environment variables are set."""
    return _get_smtp_config() is not None


def send_result_is_ok(result: SendResult) -> bool:
    """Convenience: True only when email was sent successfully."""
    return result == SendResult.OK
