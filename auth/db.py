"""
auth/db.py
----------
SQLite user database for EcoPulse AI authentication.

Schema
------
users
  id             INTEGER PRIMARY KEY AUTOINCREMENT
  full_name      TEXT    NOT NULL
  email          TEXT    NOT NULL UNIQUE
  password_hash  TEXT    NOT NULL
  created_at     TEXT    NOT NULL   (ISO-8601 UTC)
  otp_code       TEXT    NULL       (6-digit string; NULL when not active)
  otp_expires_at TEXT    NULL       (ISO-8601 UTC; NULL when not active)

Rules
-----
- Passwords are NEVER stored in plaintext. Only bcrypt hashes.
- OTP is cleared (set to NULL) immediately after successful verification.
- The database file lives at data/users.sqlite (gitignored).
- This module never prints or logs passwords, OTPs, or hashes.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import bcrypt

DB_PATH = str(Path(__file__).parent.parent / "data" / "users.sqlite")

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name       TEXT    NOT NULL,
    email           TEXT    NOT NULL UNIQUE,
    password_hash   TEXT    NOT NULL,
    created_at      TEXT    NOT NULL,
    otp_code        TEXT,
    otp_expires_at  TEXT
);
"""


def _connect() -> sqlite3.Connection:
    """Open a connection to the SQLite database, creating the file if needed."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the users table if it does not already exist."""
    with _connect() as conn:
        conn.execute(_CREATE_TABLE_SQL)
        conn.commit()


# ---------------------------------------------------------------------------
# User creation
# ---------------------------------------------------------------------------

def create_user(full_name: str, email: str, password: str) -> bool:
    """
    Insert a new user with a bcrypt-hashed password.

    Parameters
    ----------
    full_name : str
    email     : str  Must be unique.
    password  : str  Plaintext — hashed immediately, not stored.

    Returns
    -------
    True  if the user was created.
    False if the email already exists.
    """
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    now = datetime.now(timezone.utc).isoformat()
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO users (full_name, email, password_hash, created_at) "
                "VALUES (?, ?, ?, ?)",
                (full_name.strip(), email.strip().lower(), hashed, now),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False  # duplicate email


# ---------------------------------------------------------------------------
# Login / password verification
# ---------------------------------------------------------------------------

def verify_password(email: str, password: str) -> dict | None:
    """
    Check a plaintext password against the stored bcrypt hash.

    Returns
    -------
    dict with {id, full_name, email}  if credentials are correct.
    None                              if email not found or password wrong.
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, full_name, email, password_hash FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()

    if row is None:
        return None

    if not bcrypt.checkpw(password.encode(), row["password_hash"].encode()):
        return None

    return {"id": row["id"], "full_name": row["full_name"], "email": row["email"]}


# ---------------------------------------------------------------------------
# OTP management
# ---------------------------------------------------------------------------

def store_otp(email: str, otp_code: str, expires_at: datetime) -> bool:
    """
    Store an OTP code and its expiry time for a given email.

    Returns True if the user was found and updated, False otherwise.
    """
    with _connect() as conn:
        cursor = conn.execute(
            "UPDATE users SET otp_code = ?, otp_expires_at = ? WHERE email = ?",
            (otp_code, expires_at.isoformat(), email.strip().lower()),
        )
        conn.commit()
        return cursor.rowcount == 1


def verify_otp(email: str, otp_code: str) -> bool:
    """
    Verify a submitted OTP against the stored value and expiry.

    Returns True if the OTP is correct and not expired.
    Clears the OTP from the database on success (single-use).
    """
    with _connect() as conn:
        row = conn.execute(
            "SELECT otp_code, otp_expires_at FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()

    if row is None or row["otp_code"] is None:
        return False

    if row["otp_code"] != otp_code.strip():
        return False

    expires_at = datetime.fromisoformat(row["otp_expires_at"])
    # Make both timezone-aware for comparison
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expires_at:
        return False

    # Clear OTP — single use
    with _connect() as conn:
        conn.execute(
            "UPDATE users SET otp_code = NULL, otp_expires_at = NULL WHERE email = ?",
            (email.strip().lower(),),
        )
        conn.commit()
    return True


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------

def reset_password(email: str, new_password: str) -> bool:
    """
    Set a new bcrypt-hashed password for a user.

    Returns True if the user was found and updated.
    """
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    with _connect() as conn:
        cursor = conn.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (hashed, email.strip().lower()),
        )
        conn.commit()
        return cursor.rowcount == 1


# ---------------------------------------------------------------------------
# Profile update
# ---------------------------------------------------------------------------

def update_full_name(email: str, new_name: str) -> bool:
    """Update the display name for a user. Returns True on success."""
    with _connect() as conn:
        cursor = conn.execute(
            "UPDATE users SET full_name = ? WHERE email = ?",
            (new_name.strip(), email.strip().lower()),
        )
        conn.commit()
        return cursor.rowcount == 1


def get_user_by_email(email: str) -> dict | None:
    """Return {id, full_name, email, created_at} for the given email, or None."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, full_name, email, created_at FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def email_exists(email: str) -> bool:
    """Return True if the email is already registered."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()
    return row is not None
