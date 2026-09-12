"""
auth/otp.py
-----------
6-digit OTP generation and management for EcoPulse AI.

Security properties
-------------------
- Uses secrets.randbelow for cryptographically secure random integers.
- OTPs are 6 digits: 000000–999999, zero-padded.
- Each OTP expires 5 minutes after generation.
- OTPs are single-use: cleared from the database on successful verification.
- This module never prints, logs, or exposes OTP values except by returning
  them to the caller (auth/pages/forgot_password.py), which sends them via
  email only.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone


OTP_EXPIRY_MINUTES = 5


def generate_otp() -> tuple[str, datetime]:
    """
    Generate a cryptographically secure 6-digit OTP.

    Returns
    -------
    (otp_code, expires_at)
        otp_code   : str      Zero-padded 6-digit string e.g. "042817"
        expires_at : datetime UTC-aware expiry time (now + 5 minutes)
    """
    code = secrets.randbelow(1_000_000)  # 0 to 999999
    otp_code = f"{code:06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES)
    return otp_code, expires_at


def is_valid_otp_format(otp: str) -> bool:
    """Return True if the string is exactly 6 digits."""
    return isinstance(otp, str) and len(otp) == 6 and otp.isdigit()
