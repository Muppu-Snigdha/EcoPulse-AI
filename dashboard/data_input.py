"""
dashboard/data_input.py
-----------------------
Data Input page — Demo CSV, Upload CSV, Manual entry.
Extracted from app.py sidebar into its own full page.
"""
from __future__ import annotations
import io
import pandas as pd
import streamlit as st
from modules.data_loader import load_csv, validate_dataframe
from modules.anomaly import detect_all
from modules.agent import tools as tools_module

DEMO_CSV_PATH = "data/raw/campus_energy.csv"


def _load_and_cache(df: pd.DataFrame, source: str) -> None:
    clean, report = validate_dataframe(df)
    anomalies = detect_all(clean) if report["ok"] else []
    st.session_state.df = clean
    st.session_state.anomalies = anomalies
    st.session_state.validation_report = report
    st.session_state.data_source = source
    tools_module.initialise(clean)


def render() -> None:
    st.markdown("""
    <div class="ep-page-header">
        <div class="ep-page-title">📂 Data Input</div>
        <div class="ep-page-subtitle">
            Choose how to load energy data — demo dataset, CSV upload, or manual entry
        </div>
    </div>
    """, unsafe_allow_html=True)

    current = st.session_state.get("data_source", "demo")

    tab1, tab2, tab3 = st.tabs(["🏫 Demo Data", "📁 Upload CSV", "✏️ Manual Entry"])

    # ---- Tab 1: Demo -------------------------------------------------------
    with tab1:
        st.markdown("""
        <div class="ep-demo-badge">🏫 Synthetic Campus Dataset</div>
        <div class="ep-card">
            <div class="ep-card-title">Synthetic Campus Data (2023)</div>
            <div class="ep-card-subtitle">
                8 buildings × 12 months · Includes seasonal variation · One deliberate anomaly injected
            </div>
        </div>
        """, unsafe_allow_html=True)

        col_schema, col_btn = st.columns([3, 1])
        with col_schema:
            st.markdown("""
            **Dataset schema:**
            | Column | Description |
            |---|---|
            | `month` | YYYY-MM (Jan–Dec 2023) |
            | `building_id` | e.g. CSE-Block, EE-Block |
            | `department` | e.g. Computer Science, Hostel |
            | `kwh_consumed` | Monthly electricity (kWh) |
            | `occupancy_rate` | Fraction 0–1 |
            | `area_sqm` | Gross floor area (m²) |
            """)
        with col_btn:
            st.markdown("<br><br>", unsafe_allow_html=True)
            if st.button("Load Demo Data", use_container_width=True, type="primary"):
                try:
                    df_raw, _ = load_csv(DEMO_CSV_PATH)
                    _load_and_cache(df_raw, "demo")
                    st.success(f"✅ Demo data loaded — 96 rows, 8 buildings.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not load demo data: {exc}")

        if current == "demo" and st.session_state.get("df") is not None:
            st.markdown(
                '<div class="ep-status-pill ep-status-ok" style="display:inline-flex;margin-top:8px;">'
                '✅ Demo data currently active</div>',
                unsafe_allow_html=True,
            )

    # ---- Tab 2: Upload CSV -------------------------------------------------
    with tab2:
        st.markdown("""
        <div class="ep-card">
            <div class="ep-card-title">Upload Your Own CSV</div>
            <div class="ep-card-subtitle">
                Works for any location — home, office, college, campus.
                Data stays in your browser session only and is never saved to disk.
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        **Required columns (same schema as demo):**
        `month`, `building_id`, `department`, `kwh_consumed`, `occupancy_rate`, `area_sqm`
        """)

        uploaded = st.file_uploader(
            "Drop your CSV here",
            type=["csv"],
            help="Max size: 200 MB. All data is held in session only — not stored.",
            label_visibility="collapsed",
        )
        if uploaded is not None:
            if st.button("Load Uploaded CSV", use_container_width=True, type="primary"):
                try:
                    raw = pd.read_csv(io.StringIO(uploaded.read().decode("utf-8")))
                    _load_and_cache(raw, "upload")
                    st.success(f"✅ Uploaded CSV loaded — {len(st.session_state.df)} rows.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not read file: {exc}")

        # Validation warnings
        if st.session_state.get("validation_report") and current == "upload":
            rpt = st.session_state.validation_report
            if rpt["warnings"]:
                with st.expander(f"⚠️ {len(rpt['warnings'])} validation warning(s)", expanded=False):
                    for w in rpt["warnings"]:
                        st.caption(w)

        if current == "upload" and st.session_state.get("df") is not None:
            st.markdown(
                '<div class="ep-status-pill ep-status-ok" style="display:inline-flex;margin-top:8px;">'
                '✅ Uploaded data currently active</div>',
                unsafe_allow_html=True,
            )

    # ---- Tab 3: Manual Entry -----------------------------------------------
    with tab3:
        st.markdown("""
        <div class="ep-card">
            <div class="ep-card-title">Manual Meter / Bill Entry</div>
            <div class="ep-card-subtitle">
                Enter readings one row at a time. Suitable for home, small office, or single building analysis.
            </div>
        </div>
        """, unsafe_allow_html=True)

        if "manual_rows" not in st.session_state:
            st.session_state.manual_rows = []

        with st.form("manual_entry_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                month = st.text_input("Month (YYYY-MM)", value="2023-01", placeholder="2023-06")
                building_id = st.text_input("Location Name", value="", placeholder="My Home / Office A")
                department = st.text_input("Type", value="", placeholder="Home / Office / Campus Block")
            with col2:
                kwh = st.number_input("kWh Consumed", min_value=0.0, value=0.0, step=10.0)
                occupancy = st.slider("Occupancy Rate (0 = empty, 1 = full)", 0.0, 1.0, 0.8, 0.05)
                area = st.number_input("Floor Area (m²)", min_value=1.0, value=80.0, step=5.0)
            submitted = st.form_submit_button("➕ Add Row", use_container_width=True, type="primary")
            if submitted:
                if not building_id.strip():
                    st.error("Location name is required.")
                elif kwh <= 0:
                    st.error("kWh must be greater than 0.")
                else:
                    st.session_state.manual_rows.append({
                        "month": month,
                        "building_id": building_id.strip(),
                        "department": department.strip() or "General",
                        "kwh_consumed": float(kwh),
                        "occupancy_rate": float(occupancy),
                        "area_sqm": float(area),
                    })
                    st.success(f"Added: {building_id} / {month}")

        if st.session_state.manual_rows:
            st.caption(f"📋 {len(st.session_state.manual_rows)} row(s) staged")
            preview = pd.DataFrame(st.session_state.manual_rows)
            st.dataframe(preview, use_container_width=True, hide_index=True)

            col_load, col_clear = st.columns(2)
            with col_load:
                if st.button("✅ Load Manual Data", use_container_width=True, type="primary"):
                    df_manual = pd.DataFrame(st.session_state.manual_rows)
                    _load_and_cache(df_manual, "manual")
                    st.success(f"✅ Manual data loaded — {len(df_manual)} rows.")
                    st.rerun()
            with col_clear:
                if st.button("🗑️ Clear All Entries", use_container_width=True):
                    st.session_state.manual_rows = []
                    st.rerun()

        if current == "manual" and st.session_state.get("df") is not None:
            st.markdown(
                '<div class="ep-status-pill ep-status-ok" style="display:inline-flex;margin-top:8px;">'
                '✅ Manual data currently active</div>',
                unsafe_allow_html=True,
            )
