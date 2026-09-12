"""
app.py
------
EcoPulse AI — Streamlit entry point.

Auth gate: renders login/signup/forgot-password pages when not authenticated.
Dashboard: renders the selected page when authenticated.

Data source modes: Demo CSV / Upload CSV / Manual entry (moved to Data Input page).
"""

from __future__ import annotations

import os
import io

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from auth.db import init_db
from auth.session import init_auth_state, is_authenticated, logout, current_user
from modules.data_loader import load_csv, validate_dataframe
from modules.anomaly import detect_all
from modules.agent import tools as tools_module
from modules.rag.retriever import is_ready as rag_is_ready
from styles.theme import inject_css

load_dotenv()

# ---------------------------------------------------------------------------
# Page config — called ONCE, before anything else
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="EcoPulse AI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEMO_CSV_PATH = "data/raw/campus_energy.csv"


# ---------------------------------------------------------------------------
# Session state bootstrap
# ---------------------------------------------------------------------------

def _init_session_state() -> None:
    init_auth_state()
    defaults = {
        "df": None,
        "anomalies": None,
        "data_source": "demo",
        "validation_report": None,
        "manual_rows": [],
        "auth_page": "login",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _load_and_cache(df: pd.DataFrame) -> None:
    """Validate df, run anomaly detection, cache in session_state, init tools."""
    clean, report = validate_dataframe(df)
    anomalies = detect_all(clean) if report["ok"] else []
    st.session_state.df = clean
    st.session_state.anomalies = anomalies
    st.session_state.validation_report = report
    tools_module.initialise(clean)


def _ensure_data_loaded() -> None:
    """Auto-load demo data on first authenticated visit if nothing loaded yet."""
    if st.session_state.df is None and st.session_state.data_source == "demo":
        try:
            df_raw, _ = load_csv(DEMO_CSV_PATH)
            _load_and_cache(df_raw)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Auth routing
# ---------------------------------------------------------------------------

def _render_auth() -> None:
    """Show the appropriate unauthenticated page."""
    page = st.session_state.get("auth_page", "login")
    if page == "signup":
        from auth.pages.signup import render
        render()
    elif page == "forgot":
        from auth.pages.forgot_password import render
        render()
    else:
        from auth.pages.login import render
        render()


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def _render_sidebar() -> str:
    """Render the authenticated sidebar. Returns the selected page name."""
    user = current_user()
    initials = "".join(w[0].upper() for w in user["name"].split()[:2]) if user["name"] else "?"

    with st.sidebar:
        # Logo
        st.markdown(f"""
        <div class="ep-sidebar-logo">
            <div class="ep-sidebar-logo-icon">⚡</div>
            <div>
                <div class="ep-sidebar-logo-text">EcoPulse AI</div>
                <div class="ep-sidebar-logo-sub">Energy Intelligence</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # User badge
        st.markdown(f"""
        <div class="ep-user-badge">
            <div class="ep-user-avatar">{initials}</div>
            <div class="ep-user-info">
                <div class="ep-user-name">{user["name"]}</div>
                <div class="ep-user-email">{user["email"]}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="ep-nav-label">Dashboard</div>', unsafe_allow_html=True)

        # Main navigation
        page = st.radio(
            "nav",
            [
                "📊 Overview",
                "📈 Monthly Trends",
                "🏢 Building Analysis",
                "⚠️ Anomalies & Recommendations",
                "🤖 AI Assistant",
            ],
            label_visibility="collapsed",
            key="nav_main",
        )

        st.markdown('<div class="ep-nav-label">Settings</div>', unsafe_allow_html=True)

        settings_page = st.radio(
            "nav_settings",
            ["📂 Data Input", "👤 Profile"],
            label_visibility="collapsed",
            key="nav_settings",
        )

        st.markdown('<div class="ep-divider"></div>', unsafe_allow_html=True)

        # Logout
        if st.button("🚪 Logout", use_container_width=True, key="logout_btn"):
            logout()
            st.rerun()

        st.markdown('<div class="ep-divider"></div>', unsafe_allow_html=True)

        # System status
        _render_sidebar_status()

    # Merge navigation choices
    if settings_page in ["📂 Data Input", "👤 Profile"]:
        # If user clicked a settings radio, use that
        # We detect which was last clicked via a simple trick:
        # settings radio only returns its value when it was touched
        selected = settings_page
    else:
        selected = page

    # Determine which was actually most recently selected
    # Use a dedicated key to track last-clicked group
    if "last_nav_group" not in st.session_state:
        st.session_state.last_nav_group = "main"

    # Check if settings was changed by comparing to previous value
    prev_settings = st.session_state.get("_prev_settings_page", None)
    prev_main = st.session_state.get("_prev_main_page", None)

    if settings_page != prev_settings and prev_settings is not None:
        st.session_state.last_nav_group = "settings"
        st.session_state._prev_settings_page = settings_page
        st.session_state._prev_main_page = page
        return settings_page

    if page != prev_main and prev_main is not None:
        st.session_state.last_nav_group = "main"
        st.session_state._prev_main_page = page
        st.session_state._prev_settings_page = settings_page
        return page

    # First run — set defaults
    st.session_state._prev_settings_page = settings_page
    st.session_state._prev_main_page = page

    if st.session_state.last_nav_group == "settings":
        return settings_page
    return page


def _render_sidebar_status() -> None:
    """Show RAG / API key / data source status in the sidebar."""
    # Data source badge
    source = st.session_state.data_source
    if source == "demo":
        st.markdown(
            '<div class="ep-status-pill ep-status-ok">🏫 Synthetic campus data</div>',
            unsafe_allow_html=True,
        )
    elif source == "upload":
        st.markdown(
            '<div class="ep-status-pill ep-status-ok">📁 Uploaded CSV</div>',
            unsafe_allow_html=True,
        )
    elif source == "manual":
        st.markdown(
            '<div class="ep-status-pill ep-status-ok">✏️ Manual entry</div>',
            unsafe_allow_html=True,
        )

    # RAG status
    if rag_is_ready():
        st.markdown(
            '<div class="ep-status-pill ep-status-ok">🔍 Knowledge base ready</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="ep-status-pill ep-status-warn">⚠️ Knowledge base not built</div>',
            unsafe_allow_html=True,
        )
        st.caption("Run: `python -m modules.rag.ingest`")

    # API key
    if os.getenv("GEMINI_API_KEY"):
        st.markdown(
            '<div class="ep-status-pill ep-status-ok">🔑 Gemini API connected</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="ep-status-pill ep-status-err">🔑 GEMINI_API_KEY missing</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<br>', unsafe_allow_html=True)
    st.caption("EcoPulse AI · Local-first · ₹0 budget")


# ---------------------------------------------------------------------------
# Page routing
# ---------------------------------------------------------------------------

def _route_page(page: str) -> None:
    df = st.session_state.df
    anomalies = st.session_state.anomalies or []

    if page == "📊 Overview":
        from dashboard.overview import render
        render(df, anomalies)

    elif page == "📈 Monthly Trends":
        from dashboard.trends import render
        render(df, anomalies)

    elif page == "🏢 Building Analysis":
        from dashboard.buildings import render
        render(df, anomalies)

    elif page == "⚠️ Anomalies & Recommendations":
        from dashboard.recommendations import render
        render(df, anomalies)

    elif page == "🤖 AI Assistant":
        from dashboard.chat import render
        render(df, anomalies)

    elif page == "📂 Data Input":
        from dashboard.data_input import render
        render()

    elif page == "👤 Profile":
        from dashboard.profile import render
        render()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    inject_css()
    init_db()
    _init_session_state()

    if not is_authenticated():
        _render_auth()
        return

    # Authenticated — ensure data is loaded
    _ensure_data_loaded()

    page = _render_sidebar()

    if st.session_state.df is None and page not in ("📂 Data Input", "👤 Profile"):
        st.markdown("""
        <div class="ep-page-header">
            <div class="ep-page-title">⚡ EcoPulse AI</div>
            <div class="ep-page-subtitle">No data loaded yet</div>
        </div>
        """, unsafe_allow_html=True)
        st.info(
            "No data loaded. Go to **Data Input** in the sidebar to load the demo dataset, "
            "upload a CSV, or enter readings manually.",
            icon="📂",
        )
        return

    _route_page(page)


if __name__ == "__main__":
    main()
