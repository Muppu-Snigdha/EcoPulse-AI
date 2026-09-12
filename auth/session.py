"""
auth/session.py
---------------
Session state helpers for EcoPulse AI authentication.

Keys managed in st.session_state
---------------------------------
authenticated  : bool    True when a user is logged in
user_email     : str     Logged-in user's email
user_name      : str     Logged-in user's display name

None of these are written to disk — they live only in the browser session.
"""

from __future__ import annotations

import streamlit as st


def init_auth_state() -> None:
    """Ensure auth keys exist in session_state with safe defaults."""
    defaults = {
        "authenticated": False,
        "user_email": "",
        "user_name": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def login(email: str, full_name: str) -> None:
    """Mark the session as authenticated."""
    st.session_state.authenticated = True
    st.session_state.user_email = email
    st.session_state.user_name = full_name


def logout() -> None:
    """Clear all session state and mark as unauthenticated."""
    # Preserve a clean slate — wipe everything
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    # Re-initialise to safe defaults
    st.session_state.authenticated = False
    st.session_state.user_email = ""
    st.session_state.user_name = ""


def is_authenticated() -> bool:
    """Return True if the current session has a logged-in user."""
    return bool(st.session_state.get("authenticated", False))


def current_user() -> dict:
    """Return {email, name} for the logged-in user."""
    return {
        "email": st.session_state.get("user_email", ""),
        "name": st.session_state.get("user_name", ""),
    }
