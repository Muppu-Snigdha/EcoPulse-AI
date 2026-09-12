"""
styles/theme.py
---------------
EcoPulse AI — dark premium design system.

Inject all CSS via inject_css() at the top of app.py.
All class names are prefixed with `ep-` to avoid collisions with Streamlit.

Design tokens
-------------
Background      : #0a0f1e   (deep navy-black)
Surface         : #111827   (dark card background)
Surface-2       : #1a2235   (slightly lighter, for nested elements)
Border          : #1f2d3d
Border-hover    : #2d4060
Primary         : #10b981   (emerald green)
Primary-dark    : #059669
Primary-glow    : rgba(16,185,129,0.15)
Text-primary    : #f1f5f9
Text-secondary  : #cbd5e1
Text-muted      : #94a3b8
Danger          : #ef4444
Danger-bg       : rgba(239,68,68,0.08)
Warning         : #f59e0b
Warning-bg      : rgba(245,158,11,0.08)
Info            : #3b82f6
Info-bg         : rgba(59,130,246,0.08)
"""

from __future__ import annotations

import streamlit as st


# ---------------------------------------------------------------------------
# Chart theming — shared Plotly layout defaults
# ---------------------------------------------------------------------------
# PLOTLY_DARK_LAYOUT intentionally omits 'xaxis', 'yaxis', 'legend', and 'margin'
# so that each chart can pass its own values for those keys without hitting
# Plotly 6.x's strict "multiple values for keyword argument" TypeError.
PLOTLY_DARK_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#cbd5e1", family="-apple-system, 'Segoe UI', sans-serif", size=12),
    hoverlabel=dict(bgcolor="#1a2235", bordercolor="#10b981", font=dict(color="#f1f5f9")),
    colorway=["#10b981", "#3b82f6", "#f59e0b", "#ec4899", "#8b5cf6", "#06b6d4", "#f97316", "#84cc16"],
)

# Default axis style — apply via fig.update_xaxes(**PLOTLY_AXIS_STYLE) after update_layout
PLOTLY_AXIS_STYLE = dict(gridcolor="#1f2d3d", linecolor="#1f2d3d", tickcolor="#94a3b8")

# Default legend style
PLOTLY_LEGEND_DEFAULT = dict(bgcolor="rgba(0,0,0,0)", bordercolor="#1f2d3d")

# Standard chart margin
PLOTLY_MARGIN_DEFAULT = dict(t=30, b=30, l=10, r=10)

PLOTLY_GREEN_SEQ = ["#064e3b", "#065f46", "#047857", "#059669", "#10b981",
                    "#34d399", "#6ee7b7", "#a7f3d0", "#d1fae5"]


def inject_css() -> None:
    """Inject the full EcoPulse AI CSS design system into the Streamlit app."""
    st.markdown(_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Full CSS
# ---------------------------------------------------------------------------
_CSS = """
<style>
/* =========================================================
   GLOBAL RESET & BASE
   ========================================================= */
:root {
    --ep-bg:          #0a0f1e;
    --ep-surface:     #111827;
    --ep-surface2:    #1a2235;
    --ep-border:      #1f2d3d;
    --ep-border-h:    #2d4060;
    --ep-primary:     #10b981;
    --ep-primary-dk:  #059669;
    --ep-primary-glo: rgba(16,185,129,0.15);
    --ep-text:        #f1f5f9;
    --ep-text-2:      #cbd5e1;
    --ep-muted:       #94a3b8;
    --ep-danger:      #ef4444;
    --ep-warning:     #f59e0b;
    --ep-info:        #3b82f6;
    --ep-radius:      12px;
    --ep-radius-sm:   8px;
    --ep-font:        -apple-system, 'Segoe UI', system-ui, sans-serif;
}

/* App background */
.stApp, .main, [data-testid="stAppViewContainer"] {
    background-color: var(--ep-bg) !important;
    color: var(--ep-text) !important;
    font-family: var(--ep-font) !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--ep-surface); }
::-webkit-scrollbar-thumb { background: var(--ep-border-h); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--ep-primary); }

/* =========================================================
   SIDEBAR
   ========================================================= */
[data-testid="stSidebar"] {
    background: #0d1526 !important;
    border-right: 1px solid var(--ep-border) !important;
}

[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span {
    color: var(--ep-text-2) !important;
}

/* Sidebar logo section */
.ep-sidebar-logo {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 4px 0 12px;
    border-bottom: 1px solid var(--ep-border);
    margin-bottom: 12px;
}
.ep-sidebar-logo-icon {
    font-size: 28px;
    line-height: 1;
}
.ep-sidebar-logo-text {
    font-size: 18px;
    font-weight: 800;
    color: var(--ep-primary) !important;
    letter-spacing: 0.3px;
}
.ep-sidebar-logo-sub {
    font-size: 11px;
    color: var(--ep-muted) !important;
    margin-top: 1px;
}

/* Sidebar user badge */
.ep-user-badge {
    display: flex;
    align-items: center;
    gap: 10px;
    background: var(--ep-surface);
    border: 1px solid var(--ep-border);
    border-radius: var(--ep-radius-sm);
    padding: 10px 12px;
    margin-bottom: 4px;
}
.ep-user-avatar {
    width: 34px;
    height: 34px;
    background: linear-gradient(135deg, var(--ep-primary), var(--ep-primary-dk));
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 15px;
    font-weight: 700;
    color: #fff;
    flex-shrink: 0;
}
.ep-user-info { min-width: 0; }
.ep-user-name {
    font-size: 13px;
    font-weight: 600;
    color: var(--ep-text) !important;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.ep-user-email {
    font-size: 11px;
    color: var(--ep-muted) !important;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

/* Nav section label */
.ep-nav-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: var(--ep-muted) !important;
    padding: 12px 0 4px;
}

/* Status pills */
.ep-status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 20px;
    font-weight: 500;
    margin: 2px 0;
}
.ep-status-ok {
    background: rgba(16,185,129,0.12);
    color: #34d399;
    border: 1px solid rgba(16,185,129,0.25);
}
.ep-status-warn {
    background: rgba(245,158,11,0.12);
    color: #fbbf24;
    border: 1px solid rgba(245,158,11,0.25);
}
.ep-status-err {
    background: rgba(239,68,68,0.12);
    color: #f87171;
    border: 1px solid rgba(239,68,68,0.25);
}

/* =========================================================
   BUTTONS
   ========================================================= */
.stButton > button {
    background: var(--ep-surface) !important;
    color: var(--ep-text-2) !important;
    border: 1px solid var(--ep-border) !important;
    border-radius: var(--ep-radius-sm) !important;
    font-family: var(--ep-font) !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    padding: 8px 16px !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    border-color: var(--ep-primary) !important;
    color: var(--ep-primary) !important;
    background: var(--ep-primary-glo) !important;
}

/* Primary button */
.stButton > button[kind="primary"],
button[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, var(--ep-primary), var(--ep-primary-dk)) !important;
    color: #fff !important;
    border: none !important;
    font-weight: 600 !important;
    box-shadow: 0 4px 15px rgba(16,185,129,0.3) !important;
}
.stButton > button[kind="primary"]:hover,
button[data-testid="baseButton-primary"]:hover {
    box-shadow: 0 6px 20px rgba(16,185,129,0.45) !important;
    transform: translateY(-1px) !important;
}

/* =========================================================
   INPUTS
   ========================================================= */
.stTextInput input,
.stTextArea textarea,
.stSelectbox select,
.stNumberInput input {
    background: var(--ep-surface2) !important;
    border: 1px solid var(--ep-border) !important;
    border-radius: var(--ep-radius-sm) !important;
    color: var(--ep-text) !important;
    font-family: var(--ep-font) !important;
    font-size: 14px !important;
    padding: 10px 14px !important;
}
.stTextInput input:focus,
.stTextArea textarea:focus {
    border-color: var(--ep-primary) !important;
    box-shadow: 0 0 0 3px var(--ep-primary-glo) !important;
    outline: none !important;
}
.stTextInput label,
.stTextArea label,
.stSelectbox label,
.stNumberInput label,
.stSlider label {
    color: var(--ep-text-2) !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    margin-bottom: 4px !important;
}

/* Selectbox */
[data-baseweb="select"] > div {
    background: var(--ep-surface2) !important;
    border-color: var(--ep-border) !important;
    border-radius: var(--ep-radius-sm) !important;
    color: var(--ep-text) !important;
}
[data-baseweb="select"] span { color: var(--ep-text) !important; }
[data-baseweb="popover"] { background: var(--ep-surface) !important; }
[data-baseweb="menu"] { background: var(--ep-surface) !important; border-color: var(--ep-border) !important; }
[data-baseweb="menu"] li:hover { background: var(--ep-surface2) !important; }
[data-baseweb="menu"] li { color: var(--ep-text) !important; }

/* File uploader */
[data-testid="stFileUploader"] {
    background: var(--ep-surface2) !important;
    border: 2px dashed var(--ep-border) !important;
    border-radius: var(--ep-radius) !important;
    color: var(--ep-text-2) !important;
}
[data-testid="stFileUploader"]:hover { border-color: var(--ep-primary) !important; }

/* =========================================================
   FORMS
   ========================================================= */
[data-testid="stForm"] {
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}

/* =========================================================
   METRICS / KPI CARDS
   ========================================================= */
[data-testid="stMetric"] {
    background: var(--ep-surface) !important;
    border: 1px solid var(--ep-border) !important;
    border-top: 3px solid var(--ep-primary) !important;
    border-radius: var(--ep-radius) !important;
    padding: 20px 20px 16px !important;
    transition: border-color 0.2s;
}
[data-testid="stMetric"]:hover {
    border-color: var(--ep-primary) !important;
    border-top-color: var(--ep-primary) !important;
    box-shadow: 0 4px 20px rgba(16,185,129,0.1) !important;
}
[data-testid="stMetricLabel"] {
    color: var(--ep-muted) !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.8px !important;
}
[data-testid="stMetricValue"] {
    color: var(--ep-text) !important;
    font-size: 26px !important;
    font-weight: 700 !important;
}
[data-testid="stMetricDelta"] { font-size: 12px !important; font-weight: 500 !important; }

/* KPI danger variant */
.ep-kpi-danger [data-testid="stMetric"] {
    border-top-color: var(--ep-danger) !important;
}

/* =========================================================
   PAGE HEADERS
   ========================================================= */
.ep-page-header {
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--ep-border);
}
.ep-page-title {
    font-size: 24px;
    font-weight: 800;
    color: var(--ep-text);
    margin: 0 0 4px;
    letter-spacing: -0.3px;
}
.ep-page-subtitle {
    font-size: 13px;
    color: var(--ep-muted);
    margin: 0;
}

/* =========================================================
   SECTION CARDS (chart/table containers)
   ========================================================= */
.ep-card {
    background: var(--ep-surface);
    border: 1px solid var(--ep-border);
    border-radius: var(--ep-radius);
    padding: 20px 20px 16px;
    margin-bottom: 20px;
}
.ep-card-title {
    font-size: 14px;
    font-weight: 700;
    color: var(--ep-text);
    margin: 0 0 4px;
    letter-spacing: 0.1px;
}
.ep-card-subtitle {
    font-size: 12px;
    color: var(--ep-muted);
    margin: 0 0 16px;
}
.ep-section-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    color: var(--ep-primary);
    margin: 0 0 8px;
}

/* =========================================================
   DATA TABLES
   ========================================================= */
[data-testid="stDataFrame"] {
    border-radius: var(--ep-radius) !important;
    overflow: hidden !important;
    border: 1px solid var(--ep-border) !important;
}
[data-testid="stDataFrame"] thead th {
    background: var(--ep-surface2) !important;
    color: var(--ep-muted) !important;
    font-size: 11px !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.8px !important;
    border-bottom: 1px solid var(--ep-border) !important;
    padding: 10px 14px !important;
}
[data-testid="stDataFrame"] tbody td {
    background: var(--ep-surface) !important;
    color: var(--ep-text-2) !important;
    font-size: 13px !important;
    border-bottom: 1px solid var(--ep-border) !important;
    padding: 10px 14px !important;
}
[data-testid="stDataFrame"] tbody tr:hover td {
    background: var(--ep-surface2) !important;
}

/* =========================================================
   ANOMALY SEVERITY BADGES & CARDS
   ========================================================= */
.ep-severity-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}
.ep-severity-HIGH {
    background: rgba(239,68,68,0.12);
    color: #f87171;
    border: 1px solid rgba(239,68,68,0.3);
}
.ep-severity-MEDIUM {
    background: rgba(245,158,11,0.12);
    color: #fbbf24;
    border: 1px solid rgba(245,158,11,0.3);
}
.ep-severity-DATA_ISSUE {
    background: rgba(59,130,246,0.12);
    color: #60a5fa;
    border: 1px solid rgba(59,130,246,0.3);
}

.ep-anomaly-card {
    background: var(--ep-surface);
    border: 1px solid var(--ep-border);
    border-radius: var(--ep-radius);
    padding: 16px 18px;
    margin-bottom: 12px;
    position: relative;
    overflow: hidden;
}
.ep-anomaly-card::before {
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 4px;
    border-radius: 4px 0 0 4px;
}
.ep-anomaly-HIGH::before  { background: var(--ep-danger); }
.ep-anomaly-MEDIUM::before { background: var(--ep-warning); }
.ep-anomaly-DATA_ISSUE::before { background: var(--ep-info); }

.ep-anomaly-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
}
.ep-anomaly-title {
    font-size: 14px;
    font-weight: 700;
    color: var(--ep-text);
}
.ep-anomaly-meta {
    font-size: 12px;
    color: var(--ep-muted);
    margin-bottom: 10px;
    line-height: 1.5;
}
.ep-anomaly-evidence {
    background: var(--ep-surface2);
    border: 1px solid var(--ep-border);
    border-radius: var(--ep-radius-sm);
    padding: 10px 14px;
    margin-bottom: 10px;
    font-size: 12px;
    color: var(--ep-text-2);
}
.ep-anomaly-evidence strong { color: var(--ep-text); }
.ep-action-list {
    margin: 0;
    padding: 0 0 0 16px;
}
.ep-action-list li {
    font-size: 12px;
    color: var(--ep-text-2);
    margin-bottom: 4px;
    line-height: 1.5;
}

/* =========================================================
   CHAT INTERFACE
   ========================================================= */
.ep-chat-container {
    max-height: 60vh;
    overflow-y: auto;
    padding: 8px 0;
}

/* Chat message bubbles */
.ep-chat-msg { margin-bottom: 16px; }

.ep-chat-user {
    display: flex;
    justify-content: flex-end;
}
.ep-chat-user-bubble {
    background: linear-gradient(135deg, var(--ep-primary), var(--ep-primary-dk));
    color: #fff;
    border-radius: 18px 18px 4px 18px;
    padding: 12px 16px;
    max-width: 75%;
    font-size: 14px;
    line-height: 1.5;
    box-shadow: 0 2px 12px rgba(16,185,129,0.25);
}

.ep-chat-ai {
    display: flex;
    align-items: flex-start;
    gap: 10px;
}
.ep-chat-ai-avatar {
    width: 34px;
    height: 34px;
    background: var(--ep-surface2);
    border: 1px solid var(--ep-border);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    flex-shrink: 0;
    margin-top: 2px;
}
.ep-chat-ai-bubble {
    background: var(--ep-surface);
    border: 1px solid var(--ep-border);
    border-radius: 4px 18px 18px 18px;
    padding: 14px 16px;
    max-width: 85%;
    font-size: 14px;
    line-height: 1.65;
    color: var(--ep-text-2);
}
.ep-chat-ai-bubble p { margin: 0 0 10px; }
.ep-chat-ai-bubble p:last-child { margin-bottom: 0; }
.ep-chat-ai-bubble ul, .ep-chat-ai-bubble ol {
    margin: 8px 0;
    padding-left: 20px;
}
.ep-chat-ai-bubble li { margin-bottom: 4px; }
.ep-chat-ai-bubble strong { color: var(--ep-text); }
.ep-chat-ai-bubble code {
    background: var(--ep-surface2);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 12px;
    color: var(--ep-primary);
}

/* Sources panel */
.ep-sources-panel {
    background: var(--ep-surface2);
    border: 1px solid var(--ep-border);
    border-radius: var(--ep-radius-sm);
    padding: 10px 14px;
    margin-top: 8px;
    font-size: 12px;
    color: var(--ep-muted);
}
.ep-sources-panel strong { color: var(--ep-primary); font-size: 11px; letter-spacing: 0.5px; }
.ep-source-tag {
    display: inline-flex;
    align-items: center;
    background: rgba(16,185,129,0.08);
    border: 1px solid rgba(16,185,129,0.2);
    color: #34d399;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    margin: 2px 4px 2px 0;
    font-weight: 500;
}

/* RAI notice */
.ep-rai-notice {
    background: rgba(59,130,246,0.07);
    border: 1px solid rgba(59,130,246,0.2);
    border-radius: var(--ep-radius-sm);
    padding: 10px 14px;
    font-size: 12px;
    color: #93c5fd;
    margin-bottom: 16px;
    display: flex;
    align-items: flex-start;
    gap: 8px;
    line-height: 1.5;
}

/* Trace/explainability expander */
[data-testid="stExpander"] {
    background: var(--ep-surface2) !important;
    border: 1px solid var(--ep-border) !important;
    border-radius: var(--ep-radius-sm) !important;
    overflow: hidden;
}
[data-testid="stExpander"] summary {
    color: var(--ep-muted) !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    padding: 8px 12px !important;
}
[data-testid="stExpander"] summary:hover { color: var(--ep-text) !important; }
[data-testid="stExpander"] > div > div {
    background: var(--ep-surface2) !important;
    padding: 12px !important;
}

/* =========================================================
   AUTH PAGES
   ========================================================= */
.ep-auth-logo {
    text-align: center;
    padding: 40px 0 24px;
}
.ep-auth-icon { font-size: 48px; line-height: 1; margin-bottom: 8px; }
.ep-auth-brand {
    font-size: 26px;
    font-weight: 800;
    color: var(--ep-primary);
    letter-spacing: -0.5px;
    margin-bottom: 4px;
}
.ep-auth-tagline {
    font-size: 13px;
    color: var(--ep-muted);
    font-style: italic;
}

.ep-auth-card {
    background: var(--ep-surface);
    border: 1px solid var(--ep-border);
    border-radius: var(--ep-radius);
    padding: 28px 28px 24px;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
}
.ep-auth-title {
    font-size: 20px;
    font-weight: 700;
    color: var(--ep-text);
    margin-bottom: 20px;
}
.ep-auth-subtitle {
    font-size: 13px;
    color: var(--ep-muted);
    margin-bottom: 20px;
    line-height: 1.5;
}
.ep-auth-links {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid var(--ep-border);
}

/* =========================================================
   STREAMLIT NATIVE OVERRIDES
   ========================================================= */
h1, h2, h3, h4, h5, h6 {
    color: var(--ep-text) !important;
    font-family: var(--ep-font) !important;
}

h1 { font-size: 22px !important; font-weight: 800 !important; }
h2 { font-size: 18px !important; font-weight: 700 !important; }
h3 { font-size: 15px !important; font-weight: 600 !important; }

p, li, span, label { color: var(--ep-text-2) !important; }

/* Divider */
hr { border-color: var(--ep-border) !important; margin: 16px 0 !important; }

/* Alert boxes */
[data-testid="stAlert"] {
    border-radius: var(--ep-radius-sm) !important;
    font-size: 13px !important;
}

/* Success */
[data-testid="stAlert"][data-baseweb="notification"][kind="success"],
div.element-container div.stSuccess {
    background: rgba(16,185,129,0.08) !important;
    border: 1px solid rgba(16,185,129,0.3) !important;
    color: #6ee7b7 !important;
}
/* Error */
div.stError, [kind="error"] {
    background: var(--ep-danger-bg, rgba(239,68,68,0.08)) !important;
    border: 1px solid rgba(239,68,68,0.3) !important;
    color: #fca5a5 !important;
}
/* Info */
div.stInfo { background: rgba(59,130,246,0.08) !important; border: 1px solid rgba(59,130,246,0.3) !important; color: #93c5fd !important; }
/* Warning */
div.stWarning { background: rgba(245,158,11,0.08) !important; border: 1px solid rgba(245,158,11,0.3) !important; color: #fcd34d !important; }

/* Spinner */
[data-testid="stSpinner"] { color: var(--ep-primary) !important; }
.stSpinner > div { border-top-color: var(--ep-primary) !important; }

/* Caption */
.stCaption, [data-testid="stCaptionContainer"] p {
    color: var(--ep-muted) !important;
    font-size: 12px !important;
}

/* Tabs */
[data-testid="stTabs"] button { color: var(--ep-muted) !important; border-bottom: 2px solid transparent !important; }
[data-testid="stTabs"] button[aria-selected="true"] { color: var(--ep-primary) !important; border-bottom-color: var(--ep-primary) !important; }

/* Radio group (navigation) */
[data-testid="stRadio"] label {
    color: var(--ep-text-2) !important;
    font-size: 14px !important;
    padding: 4px 0 !important;
}
[data-testid="stRadio"] label:has(input:checked) {
    color: var(--ep-primary) !important;
    font-weight: 600 !important;
}

/* Plotly chart containers */
[data-testid="stPlotlyChart"] {
    background: var(--ep-surface) !important;
    border: 1px solid var(--ep-border) !important;
    border-radius: var(--ep-radius) !important;
    overflow: hidden;
}

/* Slider */
[data-testid="stSlider"] > div > div > div > div {
    background: var(--ep-primary) !important;
}

/* Chat input */
[data-testid="stChatInput"] textarea {
    background: var(--ep-surface) !important;
    border-color: var(--ep-border) !important;
    color: var(--ep-text) !important;
    border-radius: var(--ep-radius) !important;
}
[data-testid="stChatInput"] textarea:focus { border-color: var(--ep-primary) !important; }
[data-testid="stChatInput"] button {
    background: var(--ep-primary) !important;
    border-radius: 8px !important;
}

/* Chat message */
[data-testid="stChatMessage"] {
    background: transparent !important;
    border: none !important;
}
[data-testid="stChatMessageContent"] {
    background: var(--ep-surface) !important;
    border: 1px solid var(--ep-border) !important;
    border-radius: 4px 18px 18px 18px !important;
}
[data-testid="stChatMessageContent"][data-testid*="user"] {
    background: linear-gradient(135deg, var(--ep-primary), var(--ep-primary-dk)) !important;
    border: none !important;
    border-radius: 18px 18px 4px 18px !important;
}

/* Avatar icons */
[data-testid="chatAvatarIcon-user"] { background: var(--ep-primary-dk) !important; }
[data-testid="chatAvatarIcon-assistant"] { background: var(--ep-surface2) !important; border: 1px solid var(--ep-border) !important; }

/* =========================================================
   PROFILE PAGE
   ========================================================= */
.ep-profile-card {
    background: var(--ep-surface);
    border: 1px solid var(--ep-border);
    border-radius: var(--ep-radius);
    padding: 28px;
    margin-bottom: 20px;
}
.ep-profile-header {
    display: flex;
    align-items: center;
    gap: 20px;
    margin-bottom: 24px;
    padding-bottom: 20px;
    border-bottom: 1px solid var(--ep-border);
}
.ep-profile-avatar-lg {
    width: 64px;
    height: 64px;
    background: linear-gradient(135deg, var(--ep-primary), var(--ep-primary-dk));
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 26px;
    font-weight: 700;
    color: #fff;
    flex-shrink: 0;
}
.ep-profile-name { font-size: 20px; font-weight: 700; color: var(--ep-text); }
.ep-profile-email { font-size: 13px; color: var(--ep-muted); margin-top: 2px; }
.ep-profile-joined { font-size: 11px; color: var(--ep-muted); margin-top: 6px; }

/* =========================================================
   DATA INPUT PAGE
   ========================================================= */
.ep-data-mode-card {
    background: var(--ep-surface);
    border: 1px solid var(--ep-border);
    border-radius: var(--ep-radius);
    padding: 20px;
    margin-bottom: 16px;
    cursor: pointer;
    transition: border-color 0.2s, box-shadow 0.2s;
}
.ep-data-mode-card:hover {
    border-color: var(--ep-primary);
    box-shadow: 0 4px 20px rgba(16,185,129,0.08);
}
.ep-data-mode-card.active {
    border-color: var(--ep-primary);
    background: rgba(16,185,129,0.04);
}
.ep-demo-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: rgba(16,185,129,0.1);
    border: 1px solid rgba(16,185,129,0.3);
    color: var(--ep-primary);
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    margin-bottom: 12px;
}

/* =========================================================
   MISC UTILITIES
   ========================================================= */
.ep-divider {
    height: 1px;
    background: var(--ep-border);
    margin: 16px 0;
}
.ep-text-primary { color: var(--ep-primary) !important; }
.ep-text-muted   { color: var(--ep-muted) !important; }
.ep-text-danger  { color: var(--ep-danger) !important; }
.ep-text-warning { color: var(--ep-warning) !important; }
.ep-badge-primary {
    background: var(--ep-primary-glo);
    color: var(--ep-primary);
    border: 1px solid rgba(16,185,129,0.3);
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
}

/* Hide Streamlit branding */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
header    { visibility: hidden; }
[data-testid="stDecoration"] { display: none; }
</style>
"""
