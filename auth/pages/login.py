"""
auth/pages/login.py
-------------------
Login page renderer for EcoPulse AI.
Renders the full-screen premium login card.
"""

from __future__ import annotations

import streamlit as st

from auth.db import verify_password, init_db
from auth.session import login


def render() -> None:
    """Render the login page. Sets session state on success."""
    init_db()

    # Auth sub-page router (login / signup / forgot)
    if "auth_page" not in st.session_state:
        st.session_state.auth_page = "login"

    _render_login_form()


def _render_login_form() -> None:
    # Centered card layout
    _, col, _ = st.columns([1, 1.6, 1])
    with col:
        # Logo + branding
        st.markdown("""
        <div class="ep-auth-logo">
            <div class="ep-auth-icon">⚡</div>
            <div class="ep-auth-brand">EcoPulse AI</div>
            <div class="ep-auth-tagline">Intelligent Energy. Sustainable Future.</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="ep-auth-title">Sign In</div>', unsafe_allow_html=True)

        with st.form("login_form", clear_on_submit=False):
            email = st.text_input(
                "Email address",
                placeholder="you@example.com",
                key="login_email",
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                key="login_password",
            )
            submitted = st.form_submit_button(
                "Sign In",
                use_container_width=True,
                type="primary",
            )

        if submitted:
            if not email or not password:
                st.error("Please enter both email and password.")
            else:
                user = verify_password(email, password)
                if user:
                    login(user["email"], user["full_name"])
                    st.rerun()
                else:
                    st.error("Invalid email or password. Please try again.")

        # Secondary links
        st.markdown('<hr style="border-color:var(--ep-border);margin:16px 0 12px;">', unsafe_allow_html=True)
        col_fp, col_su = st.columns(2)
        with col_fp:
            if st.button("Forgot Password?", use_container_width=True, key="goto_forgot"):
                st.session_state.auth_page = "forgot"
                st.rerun()
        with col_su:
            if st.button("Create Account", use_container_width=True, key="goto_signup"):
                st.session_state.auth_page = "signup"
                st.rerun()
