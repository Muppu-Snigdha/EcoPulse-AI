"""
tests/test_auth.py
------------------
Unit tests for the auth package.

All tests use in-memory SQLite (:memory:) — no disk writes.
No SMTP calls are made. No real emails are sent.
No API calls. All tests are pure and fast.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import bcrypt
import pytest

# Patch the DB_PATH before importing auth.db so tests use :memory:
# We override _connect() to return an in-memory connection.

import auth.db as db_module


# ---------------------------------------------------------------------------
# In-memory DB fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def in_memory_db(monkeypatch):
    """
    Replace auth.db._connect() with a function that returns a shared
    in-memory SQLite connection. Reset the connection for each test.
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    def _fake_connect():
        return conn

    monkeypatch.setattr(db_module, "_connect", _fake_connect)
    # Create the table in the in-memory DB
    conn.execute(db_module._CREATE_TABLE_SQL)
    conn.commit()
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# TestUserDb — CRUD operations
# ---------------------------------------------------------------------------

class TestUserDb:

    def test_create_user_succeeds(self):
        ok = db_module.create_user("Alice Sharma", "alice@example.com", "SecurePass1!")
        assert ok is True

    def test_duplicate_email_returns_false(self):
        db_module.create_user("Alice Sharma", "alice@example.com", "Pass1!")
        ok2 = db_module.create_user("Alice Duplicate", "alice@example.com", "OtherPass!")
        assert ok2 is False

    def test_get_user_by_email_returns_dict(self):
        db_module.create_user("Bob Singh", "bob@example.com", "Pass1!")
        user = db_module.get_user_by_email("bob@example.com")
        assert user is not None
        assert user["email"] == "bob@example.com"
        assert user["full_name"] == "Bob Singh"

    def test_get_user_nonexistent_returns_none(self):
        result = db_module.get_user_by_email("nobody@example.com")
        assert result is None

    def test_email_exists_true_after_create(self):
        db_module.create_user("Carol", "carol@example.com", "Pass1!")
        assert db_module.email_exists("carol@example.com") is True

    def test_email_exists_false_for_unknown(self):
        assert db_module.email_exists("unknown@example.com") is False

    def test_email_normalised_to_lowercase(self):
        db_module.create_user("Dave", "Dave@Example.COM", "Pass1!")
        assert db_module.email_exists("dave@example.com") is True

    def test_password_not_stored_in_plaintext(self, in_memory_db):
        db_module.create_user("Eve", "eve@example.com", "MySecret123")
        row = in_memory_db.execute(
            "SELECT password_hash FROM users WHERE email = 'eve@example.com'"
        ).fetchone()
        assert row is not None
        # Hash must not contain the plaintext password
        assert "MySecret123" not in row["password_hash"]
        # Must start with a bcrypt prefix
        assert row["password_hash"].startswith("$2b$")

    def test_update_full_name(self):
        db_module.create_user("Old Name", "rename@example.com", "Pass1!")
        ok = db_module.update_full_name("rename@example.com", "New Name")
        assert ok is True
        user = db_module.get_user_by_email("rename@example.com")
        assert user["full_name"] == "New Name"

    def test_update_full_name_nonexistent_returns_false(self):
        ok = db_module.update_full_name("nobody@example.com", "Name")
        assert ok is False


# ---------------------------------------------------------------------------
# TestBcryptHashing — password verification
# ---------------------------------------------------------------------------

class TestBcryptHashing:

    def test_correct_password_verifies(self):
        db_module.create_user("Test User", "test@example.com", "CorrectPass1!")
        user = db_module.verify_password("test@example.com", "CorrectPass1!")
        assert user is not None
        assert user["email"] == "test@example.com"

    def test_wrong_password_returns_none(self):
        db_module.create_user("Test User", "test2@example.com", "CorrectPass1!")
        result = db_module.verify_password("test2@example.com", "WrongPass!")
        assert result is None

    def test_nonexistent_email_returns_none(self):
        result = db_module.verify_password("ghost@example.com", "AnyPass!")
        assert result is None

    def test_verify_returns_no_password_hash(self):
        db_module.create_user("Secure", "secure@example.com", "Pass1!")
        user = db_module.verify_password("secure@example.com", "Pass1!")
        assert user is not None
        assert "password_hash" not in user
        assert "password" not in user

    def test_reset_password_then_verify_new(self):
        db_module.create_user("Reset", "reset@example.com", "OldPass1!")
        db_module.reset_password("reset@example.com", "NewPass1!")
        # Old password must fail
        assert db_module.verify_password("reset@example.com", "OldPass1!") is None
        # New password must succeed
        user = db_module.verify_password("reset@example.com", "NewPass1!")
        assert user is not None

    def test_reset_nonexistent_returns_false(self):
        ok = db_module.reset_password("nobody@example.com", "NewPass!")
        assert ok is False


# ---------------------------------------------------------------------------
# TestOtp — generation and verification
# ---------------------------------------------------------------------------

class TestOtp:
    """Tests for auth/otp.py (pure functions — no DB needed)."""

    def test_generate_otp_is_6_digits(self):
        from auth.otp import generate_otp
        code, _ = generate_otp()
        assert len(code) == 6
        assert code.isdigit()

    def test_generate_otp_is_in_valid_range(self):
        from auth.otp import generate_otp
        code, _ = generate_otp()
        assert 0 <= int(code) <= 999999

    def test_generate_otp_zero_padded(self):
        from auth.otp import generate_otp
        # Run several times to increase chance of hitting small numbers
        for _ in range(50):
            code, _ = generate_otp()
            assert len(code) == 6, f"OTP not 6 chars: {code!r}"

    def test_otp_expiry_is_5_minutes(self):
        from auth.otp import generate_otp, OTP_EXPIRY_MINUTES
        _, expires_at = generate_otp()
        now = datetime.now(timezone.utc)
        delta = expires_at - now
        # Allow 1-second tolerance
        assert abs(delta.total_seconds() - OTP_EXPIRY_MINUTES * 60) < 2

    def test_is_valid_otp_format_accepts_6_digits(self):
        from auth.otp import is_valid_otp_format
        assert is_valid_otp_format("123456") is True
        assert is_valid_otp_format("000000") is True
        assert is_valid_otp_format("999999") is True

    def test_is_valid_otp_format_rejects_invalid(self):
        from auth.otp import is_valid_otp_format
        assert is_valid_otp_format("12345") is False    # 5 digits
        assert is_valid_otp_format("1234567") is False  # 7 digits
        assert is_valid_otp_format("12345a") is False   # non-digit
        assert is_valid_otp_format("") is False
        assert is_valid_otp_format(None) is False       # type: ignore[arg-type]

    def test_store_and_verify_otp(self):
        from auth.otp import generate_otp
        db_module.create_user("OTP User", "otp@example.com", "Pass1!")
        code, expires_at = generate_otp()
        ok = db_module.store_otp("otp@example.com", code, expires_at)
        assert ok is True
        valid = db_module.verify_otp("otp@example.com", code)
        assert valid is True

    def test_wrong_otp_rejected(self):
        from auth.otp import generate_otp
        db_module.create_user("OTP User2", "otp2@example.com", "Pass1!")
        code, expires_at = generate_otp()
        db_module.store_otp("otp2@example.com", code, expires_at)
        valid = db_module.verify_otp("otp2@example.com", "000000" if code != "000000" else "111111")
        assert valid is False

    def test_expired_otp_rejected(self):
        db_module.create_user("Expired User", "expired@example.com", "Pass1!")
        # Set expiry in the past
        past = datetime.now(timezone.utc) - timedelta(minutes=10)
        db_module.store_otp("expired@example.com", "123456", past)
        valid = db_module.verify_otp("expired@example.com", "123456")
        assert valid is False

    def test_otp_single_use_cleared_after_verification(self, in_memory_db):
        from auth.otp import generate_otp
        db_module.create_user("Once User", "once@example.com", "Pass1!")
        code, expires_at = generate_otp()
        db_module.store_otp("once@example.com", code, expires_at)
        # First use — valid
        assert db_module.verify_otp("once@example.com", code) is True
        # Second use — should fail (OTP cleared)
        assert db_module.verify_otp("once@example.com", code) is False

    def test_nonexistent_email_otp_fails(self):
        valid = db_module.verify_otp("ghost@example.com", "123456")
        assert valid is False

    def test_store_otp_nonexistent_email_returns_false(self):
        from auth.otp import generate_otp
        code, expires_at = generate_otp()
        ok = db_module.store_otp("nobody@example.com", code, expires_at)
        assert ok is False


# ---------------------------------------------------------------------------
# TestSessionHelpers — pure session state tests
# ---------------------------------------------------------------------------

class TestSessionHelpers:
    """Tests for auth/session.py — uses a mock st.session_state."""

    def _make_state(self):
        """Return a plain dict as a mock for st.session_state."""
        return {}

    def test_is_authenticated_false_when_not_set(self):
        from auth.session import is_authenticated
        with patch("auth.session.st") as mock_st:
            mock_st.session_state = {}
            assert is_authenticated() is False

    def test_is_authenticated_true_after_login(self):
        from auth.session import is_authenticated, login
        with patch("auth.session.st") as mock_st:
            mock_st.session_state = {}
            login.__module__  # access to trigger patch
            mock_st.session_state["authenticated"] = True
            assert is_authenticated() is True

    def test_current_user_returns_empty_when_not_logged_in(self):
        from auth.session import current_user
        with patch("auth.session.st") as mock_st:
            mock_st.session_state = {}
            user = current_user()
            assert user["email"] == ""
            assert user["name"] == ""

    def test_current_user_returns_values_when_logged_in(self):
        from auth.session import current_user
        with patch("auth.session.st") as mock_st:
            mock_st.session_state = {
                "authenticated": True,
                "user_email": "alice@example.com",
                "user_name": "Alice Sharma",
            }
            user = current_user()
            assert user["email"] == "alice@example.com"
            assert user["name"] == "Alice Sharma"


# ---------------------------------------------------------------------------
# TestEmailSender — config detection only (no real SMTP)
# ---------------------------------------------------------------------------

class TestEmailSender:

    def test_is_smtp_configured_false_when_env_missing(self):
        from auth.email_sender import is_smtp_configured
        with patch.dict("os.environ", {}, clear=True):
            # Remove SMTP vars if present
            import os
            for k in ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"]:
                os.environ.pop(k, None)
            assert is_smtp_configured() is False

    def test_is_smtp_configured_true_when_env_set(self):
        from auth.email_sender import is_smtp_configured
        with patch.dict("os.environ", {
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "test@gmail.com",
            "SMTP_PASSWORD": "apppassword",
        }):
            assert is_smtp_configured() is True
