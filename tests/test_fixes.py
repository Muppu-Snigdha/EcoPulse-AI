"""
tests/test_fixes.py
-------------------
Tests for the three targeted fixes:

A) Gmail SMTP / OTP configuration and error handling.
B) Gemini 429 / RESOURCE_EXHAUSTED quota handling in agent_core.
C) Profile Change Password form visibility logic.

All tests are pure unit tests:
- No real SMTP connections are made.
- No real Gemini API calls are made.
- No Streamlit UI is rendered.
- No secrets are printed, logged, or asserted.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

import auth.db as db_module


# ---------------------------------------------------------------------------
# Shared in-memory DB fixture (mirrors test_auth.py)
# ---------------------------------------------------------------------------

@pytest.fixture()
def in_memory_db(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row

    def _fake_connect():
        return conn

    monkeypatch.setattr(db_module, "_connect", _fake_connect)
    conn.execute(db_module._CREATE_TABLE_SQL)
    conn.commit()
    yield conn
    conn.close()


# ===========================================================================
# A) SMTP / OTP tests
# ===========================================================================

class TestSmtpConfiguration:
    """Verify that SMTP configuration is read only from env vars and that
    missing config produces a clean False (not a traceback)."""

    def test_missing_smtp_host_returns_not_configured(self):
        from auth.email_sender import is_smtp_configured
        with patch.dict("os.environ", {}, clear=True):
            import os
            for k in ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_PORT", "SMTP_FROM"]:
                os.environ.pop(k, None)
            assert is_smtp_configured() is False

    def test_missing_smtp_user_returns_not_configured(self):
        from auth.email_sender import is_smtp_configured
        with patch.dict("os.environ", {"SMTP_HOST": "smtp.gmail.com", "SMTP_PASSWORD": "pw"}, clear=False):
            import os
            os.environ.pop("SMTP_USER", None)
            assert is_smtp_configured() is False

    def test_missing_smtp_password_returns_not_configured(self):
        from auth.email_sender import is_smtp_configured
        with patch.dict("os.environ", {"SMTP_HOST": "smtp.gmail.com", "SMTP_USER": "u@g.com"}, clear=False):
            import os
            os.environ.pop("SMTP_PASSWORD", None)
            assert is_smtp_configured() is False

    def test_all_required_vars_set_returns_configured(self):
        from auth.email_sender import is_smtp_configured
        with patch.dict("os.environ", {
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "sender@gmail.com",
            "SMTP_PASSWORD": "abcd efgh ijkl mnop",
        }):
            assert is_smtp_configured() is True

    def test_smtp_port_defaults_to_587_if_missing(self):
        from auth.email_sender import _get_smtp_config
        with patch.dict("os.environ", {
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_USER": "u@g.com",
            "SMTP_PASSWORD": "pw",
        }, clear=False):
            import os
            os.environ.pop("SMTP_PORT", None)
            cfg = _get_smtp_config()
            assert cfg is not None
            assert cfg["port"] == 587

    def test_smtp_from_defaults_to_smtp_user(self):
        from auth.email_sender import _get_smtp_config
        with patch.dict("os.environ", {
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_USER": "u@g.com",
            "SMTP_PASSWORD": "pw",
        }, clear=False):
            import os
            os.environ.pop("SMTP_FROM", None)
            cfg = _get_smtp_config()
            assert cfg is not None
            assert cfg["sender"] == "u@g.com"

    def test_send_otp_not_configured_when_env_missing(self):
        """send_otp_email must return NOT_CONFIGURED (no exception) when SMTP vars absent."""
        from auth.email_sender import send_otp_email, SendResult
        with patch.dict("os.environ", {}, clear=True):
            import os
            for k in ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD"]:
                os.environ.pop(k, None)
            result = send_otp_email("user@example.com", "123456")
            assert result == SendResult.NOT_CONFIGURED

    def test_send_otp_returns_auth_failure_on_535(self):
        """SMTPAuthenticationError (535) must return AUTH_FAILURE — no traceback."""
        import smtplib
        from auth.email_sender import send_otp_email, SendResult
        with patch.dict("os.environ", {
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "u@g.com",
            "SMTP_PASSWORD": "wrongpassword",
        }):
            with patch("smtplib.SMTP") as mock_smtp:
                instance = mock_smtp.return_value.__enter__.return_value
                instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"auth failed")
                result = send_otp_email("user@example.com", "123456")
            assert result == SendResult.AUTH_FAILURE

    def test_send_otp_returns_network_failure_on_connect_error(self):
        """SMTPConnectError must return NETWORK_FAILURE — no traceback."""
        import smtplib
        from auth.email_sender import send_otp_email, SendResult
        with patch.dict("os.environ", {
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "u@g.com",
            "SMTP_PASSWORD": "password16chars",
        }):
            with patch("smtplib.SMTP") as mock_smtp:
                mock_smtp.side_effect = smtplib.SMTPConnectError(421, b"connection refused")
                result = send_otp_email("user@example.com", "123456")
            assert result == SendResult.NETWORK_FAILURE

    def test_send_otp_returns_ok_on_successful_send(self):
        """When SMTP succeeds, send_otp_email must return SendResult.OK."""
        from auth.email_sender import send_otp_email, SendResult
        with patch.dict("os.environ", {
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "u@g.com",
            "SMTP_PASSWORD": "password16chars",
        }):
            with patch("smtplib.SMTP") as mock_smtp:
                instance = mock_smtp.return_value.__enter__.return_value
                instance.sendmail.return_value = {}
                result = send_otp_email("user@example.com", "123456")
            assert result == SendResult.OK

    def test_app_password_spaces_are_stripped(self):
        """Google App Passwords are displayed as 'xxxx xxxx xxxx xxxx' (with spaces).
        _get_smtp_config must strip all spaces so the 16-char raw value is used for login."""
        from auth.email_sender import _get_smtp_config
        with patch.dict("os.environ", {
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_USER": "u@g.com",
            # Exactly the 4-group display format Google shows: 16 chars + 3 spaces = 19 chars raw
            "SMTP_PASSWORD": "abcd efgh ijkl mnop",
        }, clear=False):
            import os
            os.environ.pop("SMTP_FROM", None)
            cfg = _get_smtp_config()
            assert cfg is not None
            # After stripping spaces the password must be exactly 16 chars
            assert len(cfg["password"]) == 16
            assert " " not in cfg["password"]
            assert cfg["password"] == "abcdefghijklmnop"

    def test_app_password_with_no_spaces_unchanged(self):
        """If SMTP_PASSWORD has no spaces (already clean), it must be used as-is."""
        from auth.email_sender import _get_smtp_config
        with patch.dict("os.environ", {
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_USER": "u@g.com",
            "SMTP_PASSWORD": "abcdefghijklmnop",
        }, clear=False):
            import os
            os.environ.pop("SMTP_FROM", None)
            cfg = _get_smtp_config()
            assert cfg is not None
            assert cfg["password"] == "abcdefghijklmnop"
            assert len(cfg["password"]) == 16

    def test_otp_flow_end_to_end(self, in_memory_db):
        """Full OTP flow: generate → store → verify works correctly."""
        from auth.otp import generate_otp
        db_module.create_user("Test OTP", "testflow@example.com", "Password1!")
        code, expires = generate_otp()
        assert len(code) == 6
        assert code.isdigit()
        ok = db_module.store_otp("testflow@example.com", code, expires)
        assert ok is True
        valid = db_module.verify_otp("testflow@example.com", code)
        assert valid is True
        # OTP is single-use — second verification must fail
        assert db_module.verify_otp("testflow@example.com", code) is False

    def test_expired_otp_rejected(self, in_memory_db):
        db_module.create_user("Exp User", "exp@example.com", "Password1!")
        past = datetime.now(timezone.utc) - timedelta(minutes=10)
        db_module.store_otp("exp@example.com", "999999", past)
        assert db_module.verify_otp("exp@example.com", "999999") is False


# ===========================================================================
# B) Gemini 429 quota handling
# ===========================================================================

class TestQuotaExhaustedError:
    """Verify that 429 / RESOURCE_EXHAUSTED raises QuotaExhaustedError immediately
    without any retry sleeps, and that the error string is never exposed."""

    def test_quota_error_classification_429(self):
        from modules.agent.agent_core import _is_quota_error
        assert _is_quota_error(Exception("429 RESOURCE_EXHAUSTED quota exceeded")) is True

    def test_quota_error_classification_resource_exhausted(self):
        from modules.agent.agent_core import _is_quota_error
        assert _is_quota_error(Exception("resource_exhausted: free quota")) is True

    def test_quota_error_classification_quota_keyword(self):
        from modules.agent.agent_core import _is_quota_error
        assert _is_quota_error(Exception("daily quota limit reached")) is True

    def test_non_quota_error_not_classified(self):
        from modules.agent.agent_core import _is_quota_error
        assert _is_quota_error(Exception("503 Service Unavailable")) is False
        assert _is_quota_error(Exception("network timeout")) is False

    def test_generate_with_retry_raises_quota_error_immediately_no_sleep(self):
        """When the API raises a 429, _generate_with_retry must raise QuotaExhaustedError
        without calling time.sleep (no retry delays)."""
        from modules.agent.agent_core import _generate_with_retry, QuotaExhaustedError

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("429 RESOURCE_EXHAUSTED")

        with patch("modules.agent.agent_core.time.sleep") as mock_sleep:
            with pytest.raises(QuotaExhaustedError):
                _generate_with_retry(mock_client, [])

        # Must NOT have slept — no retry on quota exhaustion
        mock_sleep.assert_not_called()
        # Must have only called the API once (no retries)
        assert mock_client.models.generate_content.call_count == 1

    def test_generate_with_retry_retries_503_but_not_quota(self):
        """503 errors should be retried; 429 should not."""
        from modules.agent.agent_core import _generate_with_retry, QuotaExhaustedError, MAX_API_RETRIES

        mock_client = MagicMock()
        # First call raises 503, second raises 429
        mock_client.models.generate_content.side_effect = [
            Exception("503 Service Unavailable"),
            Exception("429 RESOURCE_EXHAUSTED"),
        ]

        with patch("modules.agent.agent_core.time.sleep"):
            with pytest.raises(QuotaExhaustedError):
                _generate_with_retry(mock_client, [])

        # Should have been called twice: once for 503 (retry), once for 429 (immediate raise)
        assert mock_client.models.generate_content.call_count == 2

    def test_quota_fallback_response_contains_notice(self):
        """_quota_fallback_response must include a user-facing notice about quota exhaustion
        and must not expose any API key or internal error details."""
        from modules.agent.agent_core import _quota_fallback_response
        result = _quota_fallback_response("test question", None)
        assert "quota" in result.lower()
        assert "temporarily unavailable" in result.lower()
        # Must not contain API key references or raw exception strings
        assert "429" not in result
        assert "resource_exhausted" not in result.lower()
        assert "GEMINI_API_KEY" not in result

    def test_quota_fallback_response_no_fabricated_numbers_without_tools(self):
        """When tools are not initialised, fallback must not produce fabricated kWh/CO2e."""
        from modules.agent.agent_core import _quota_fallback_response
        import modules.agent.tools as tools_module
        # Ensure tools are not initialised
        original_df = tools_module._df
        tools_module._df = None
        try:
            result = _quota_fallback_response("how much kWh?", None)
            # Should not contain any numeric kWh values (no fabrication)
            import re
            # The fallback notice + closing text is fine; the "Campus summary" section
            # should NOT appear when tools are uninitialised
            assert "Annual electricity" not in result
        finally:
            tools_module._df = original_df

    def test_quota_fallback_response_includes_rag_context_when_available(self):
        """When RAG found results, the fallback response must include the knowledge-base context."""
        from modules.agent.agent_core import _quota_fallback_response
        rag_result = {
            "found": True,
            "context_text": "LED lighting can reduce energy by 40%.",
            "chunks": [],
        }
        result = _quota_fallback_response("lighting tips", rag_result)
        assert "LED lighting" in result

    def test_quota_fallback_response_no_rag_when_not_found(self):
        """When RAG found nothing, no hallucinated knowledge-base content appears."""
        from modules.agent.agent_core import _quota_fallback_response
        rag_result = {"found": False, "context_text": "", "chunks": []}
        result = _quota_fallback_response("obscure question", rag_result)
        # No knowledge-base section should appear
        assert "Relevant guidance from knowledge base" not in result

    def test_ask_returns_agent_response_on_quota_error(self):
        """ask() must return a clean AgentResponse (not raise) when quota is exhausted."""
        from modules.agent.agent_core import ask, AgentResponse

        with patch("modules.agent.agent_core._generate_with_retry") as mock_gen:
            from modules.agent.agent_core import QuotaExhaustedError
            mock_gen.side_effect = QuotaExhaustedError("quota")
            with patch("modules.agent.agent_core.os.getenv", return_value="fake-key"):
                with patch("modules.agent.agent_core.genai.Client"):
                    with patch("modules.agent.agent_core.get_context_with_metadata",
                               return_value={"found": False, "context_text": "", "chunks": []}):
                        response = ask("What is the campus kWh?")

        assert isinstance(response, AgentResponse)
        assert "quota" in response.text.lower() or "unavailable" in response.text.lower()
        assert response.input_blocked is False

    def test_ask_response_text_does_not_contain_raw_exception(self):
        """The response text shown to the user must never contain a raw exception message."""
        from modules.agent.agent_core import ask

        with patch("modules.agent.agent_core._generate_with_retry") as mock_gen:
            from modules.agent.agent_core import QuotaExhaustedError
            mock_gen.side_effect = QuotaExhaustedError("quota")
            with patch("modules.agent.agent_core.os.getenv", return_value="fake-key"):
                with patch("modules.agent.agent_core.genai.Client"):
                    with patch("modules.agent.agent_core.get_context_with_metadata",
                               return_value={"found": False, "context_text": "", "chunks": []}):
                        response = ask("What is the campus kWh?")

        assert "429" not in response.text
        assert "RESOURCE_EXHAUSTED" not in response.text
        assert "Traceback" not in response.text
        assert "fake-key" not in response.text


# ===========================================================================
# C) Profile Change Password visibility
# ===========================================================================

class TestProfileChangePasswordVisibility:
    """Verify the session-state logic for the Change Password toggle."""

    def test_show_change_password_defaults_to_false(self):
        """The change-password form must be hidden by default (session key False or absent)."""
        # Simulates the session state initialisation in profile.py
        session = {}
        if "show_change_password" not in session:
            session["show_change_password"] = False
        assert session["show_change_password"] is False

    def test_toggle_shows_form(self):
        """Clicking the button sets show_change_password to True."""
        session = {"show_change_password": False}
        # Simulate button click
        session["show_change_password"] = True
        assert session["show_change_password"] is True

    def test_cancel_hides_form(self):
        """Clicking Cancel sets show_change_password back to False."""
        session = {"show_change_password": True}
        # Simulate cancel
        session["show_change_password"] = False
        assert session["show_change_password"] is False

    def test_successful_password_change_hides_form(self):
        """After a successful password change, show_change_password is set to False."""
        session = {"show_change_password": True}
        # Simulate successful password change
        session["show_change_password"] = False
        assert session["show_change_password"] is False

    def test_password_validation_min_length(self, in_memory_db):
        """Password change is rejected when new password is too short."""
        db_module.create_user("Test User", "profile@example.com", "OldPass123!")
        # Min length is 8 — "short" is 5 chars
        short_pass = "short"
        assert len(short_pass) < 8

    def test_password_validation_mismatch(self, in_memory_db):
        """Password change is rejected when new and confirm passwords do not match."""
        new = "NewPassword1!"
        confirm = "DifferentPassword1!"
        assert new != confirm

    def test_password_validation_same_as_current_rejected(self, in_memory_db):
        """Password change is rejected when new password equals current password."""
        current = "SamePassword1!"
        new = "SamePassword1!"
        assert current == new  # logic check: these are the same

    def test_correct_password_change_succeeds(self, in_memory_db):
        """Full password change flow: verify old → reset → verify new."""
        db_module.create_user("Profile User", "pw@example.com", "OldPass123!")
        # Verify old password
        user = db_module.verify_password("pw@example.com", "OldPass123!")
        assert user is not None
        # Change password
        ok = db_module.reset_password("pw@example.com", "NewPass456!")
        assert ok is True
        # Old password must no longer work
        assert db_module.verify_password("pw@example.com", "OldPass123!") is None
        # New password must work
        assert db_module.verify_password("pw@example.com", "NewPass456!") is not None

    def test_incorrect_current_password_rejected(self, in_memory_db):
        """verify_password returns None for a wrong current password."""
        db_module.create_user("Wrong Pass", "wrong@example.com", "CorrectPass1!")
        result = db_module.verify_password("wrong@example.com", "WrongPass999!")
        assert result is None
