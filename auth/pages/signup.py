"""
auth/pages/signup.py
--------------------
Sign-up page renderer for EcoPulse AI.
"""

from __future__ import annotations

import re
import streamlit as st

from auth.db import create_user, email_exists, init_db
from auth.session import login

_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")
_MIN_PASSWORD_LENGTH = 8


def render() -> None:
    init_db()
    _, col, _ = st.columns([1, 1.6, 1])
    with col:
        st.markdown("""
        <div class="ep-auth-logo">
            <div class="ep-auth-icon">⚡</div>
            <div class="ep-auth-brand">EcoPulse AI</div>
            <div class="ep-auth-tagline">Intelligent Energy. Sustainable Future.</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="ep-auth-title">Create Account</div>', unsafe_allow_html=True)

        with st.form("signup_form", clear_on_submit=False):
            full_name = st.text_input("Full Name", placeholder="Your full name", key="su_name")
            email = st.text_input("Email address", placeholder="you@example.com", key="su_email")
            password = st.text_input(
                "Password",
                type="password",
                placeholder=f"Min {_MIN_PASSWORD_LENGTH} characters",
                key="su_pass",
            )
            confirm = st.text_input(
                "Confirm Password",
                type="password",
                placeholder="Repeat your password",
                key="su_confirm",
            )
            submitted = st.form_submit_button(
                "Create Account",
                use_container_width=True,
                type="primary",
            )

        if submitted:
            error = _validate_signup(full_name, email, password, confirm)
            if error:
                st.error(error)
            else:
                ok = create_user(full_name, email, password)
                if ok:
                    # Auto-login after successful registration
                    login(email.strip().lower(), full_name.strip())
                    st.success("Account created! Welcome to EcoPulse AI.")
                    st.rerun()
                else:
                    st.error("That email is already registered. Please sign in.")

        st.markdown('<hr style="border-color:var(--ep-border);margin:16px 0 12px;">', unsafe_allow_html=True)
        if st.button("← Back to Sign In", use_container_width=True, key="su_back"):
            st.session_state.auth_page = "login"
            st.rerun()


def _validate_signup(full_name: str, email: str, password: str, confirm: str) -> str | None:
    """Return an error string, or None if all fields are valid."""
    if not full_name or not full_name.strip():
        return "Full name is required."
    if not email or not _EMAIL_RE.match(email.strip()):
        return "Please enter a valid email address."
    if email_exists(email):
        return "That email is already registered. Please sign in."
    if len(password) < _MIN_PASSWORD_LENGTH:
        return f"Password must be at least {_MIN_PASSWORD_LENGTH} characters."
    if password != confirm:
        return "Passwords do not match."
    return None
