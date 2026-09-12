"""
dashboard/overview.py — Premium redesign.
All calculations unchanged. Visual layer only.
"""
from __future__ import annotations
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from modules.calculator import calc_monthly_totals, calc_building_totals, CONSTANTS
from styles.theme import (
    PLOTLY_DARK_LAYOUT,
    PLOTLY_AXIS_STYLE,
    PLOTLY_LEGEND_DEFAULT,
    PLOTLY_GREEN_SEQ,
)


def render(df, anomalies):
    # Guard: show a clean message instead of a traceback on empty / None data
    if df is None or df.empty:
        st.info("No data available. Go to **Data Input** to load or upload data.", icon="📂")
        return

    monthly = calc_monthly_totals(df)
    buildings = calc_building_totals(df)
    benchmark = CONSTANTS["eui_benchmark_kwh_m2_year"]

    total_kwh = monthly["total_kwh"].sum()
    total_co2e = monthly["total_co2e_kg"].sum()
    unique_area = df.groupby("building_id")["area_sqm"].first().sum()
    campus_eui = round(total_kwh / unique_area, 2) if unique_area > 0 else 0.0
    high_anomalies = len([a for a in anomalies if a.severity == "HIGH"])

    # ---- Page header -------------------------------------------------------
    source_label = st.session_state.get("data_source", "demo")
    source_badge = {
        "demo": '<span class="ep-badge-primary">🏫 Synthetic Demo Data</span>',
        "upload": '<span class="ep-badge-primary">📁 Uploaded CSV</span>',
        "manual": '<span class="ep-badge-primary">✏️ Manual Entry</span>',
    }.get(source_label, "")

    st.markdown(f"""
    <div class="ep-page-header">
        <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">
            <div class="ep-page-title">Campus Energy Overview</div>
            {source_badge}
        </div>
        <div class="ep-page-subtitle">
            Academic Year 2023 · {len(df["building_id"].unique())} buildings ·
            {df["month"].nunique()} months · India CEA 2023 emission factor
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ---- KPI Cards ---------------------------------------------------------
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(
        label="⚡ Total Electricity",
        value=f"{total_kwh:,.0f} kWh",
        help="Sum of all building consumption — from deterministic calculations",
    )
    c2.metric(
        label="🌿 Carbon Footprint",
        value=f"{total_co2e/1000:,.1f} tCO₂e",
        help="Scope 2 — India CEA 2023 emission factor (0.716 kg CO₂e/kWh)",
    )
    c3.metric(
        label="📐 Campus EUI",
        value=f"{campus_eui:.1f} kWh/m²",
        delta=f"{campus_eui - benchmark:.1f} vs benchmark",
        delta_color="inverse",
        help=f"Energy Use Intensity vs BEE/IEA benchmark ({benchmark} kWh/m²/yr)",
    )
    with c4:
        if high_anomalies > 0:
            st.markdown('<div class="ep-kpi-danger">', unsafe_allow_html=True)
        c4.metric(
            label="🚨 HIGH Anomalies",
            value=str(high_anomalies),
            delta="Needs attention" if high_anomalies > 0 else "All clear",
            delta_color="inverse" if high_anomalies > 0 else "normal",
            help="Buildings/months flagged by rule-based anomaly detection",
        )
        if high_anomalies > 0:
            st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ---- Charts ------------------------------------------------------------
    left, right = st.columns(2)

    with left:
        st.markdown('<div class="ep-card"><div class="ep-section-label">Consumption Distribution</div>'
                    '<div class="ep-card-title">Electricity Share by Building</div></div>', unsafe_allow_html=True)
        try:
            fig_pie = px.pie(
                buildings, names="building_id", values="total_kwh",
                color_discrete_sequence=PLOTLY_GREEN_SEQ, hole=0.42,
            )
            fig_pie.update_traces(
                textposition="inside", textinfo="percent+label",
                hovertemplate="<b>%{label}</b><br>%{value:,.0f} kWh<br>%{percent}<extra></extra>",
            )
            fig_pie.update_layout(
                **PLOTLY_DARK_LAYOUT,
                showlegend=False,
                margin=dict(t=10, b=10, l=10, r=10),
                height=320,
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        except Exception as exc:
            st.warning(f"Pie chart could not render: {exc}")

    with right:
        st.markdown('<div class="ep-card"><div class="ep-section-label">Time Series</div>'
                    '<div class="ep-card-title">Monthly kWh & Carbon Footprint</div></div>', unsafe_allow_html=True)
        try:
            fig_dual = go.Figure()
            fig_dual.add_bar(
                x=monthly["month"], y=monthly["total_kwh"],
                name="kWh", marker_color="#10b981", opacity=0.75,
                hovertemplate="<b>%{x}</b><br>%{y:,.0f} kWh<extra></extra>",
            )
            fig_dual.add_scatter(
                x=monthly["month"], y=monthly["total_co2e_kg"],
                name="CO₂e (kg)", yaxis="y2",
                line=dict(color="#ef4444", width=2.5),
                mode="lines+markers",
                marker=dict(size=6),
                hovertemplate="<b>%{x}</b><br>%{y:,.0f} kg CO₂e<extra></extra>",
            )
            fig_dual.update_layout(
                **PLOTLY_DARK_LAYOUT,
                yaxis=dict(title="kWh", gridcolor="#1f2d3d", linecolor="#1f2d3d", tickcolor="#94a3b8"),
                yaxis2=dict(title="kg CO₂e", overlaying="y", side="right", showgrid=False,
                            linecolor="#1f2d3d", tickcolor="#94a3b8"),
                legend=dict(orientation="h", yanchor="bottom", y=1.02, bgcolor="rgba(0,0,0,0)"),
                hovermode="x unified",
                height=320,
                margin=dict(t=30, b=30, l=10, r=50),
            )
            fig_dual.update_xaxes(**PLOTLY_AXIS_STYLE)
            st.plotly_chart(fig_dual, use_container_width=True)
        except Exception as exc:
            st.warning(f"Monthly trend chart could not render: {exc}")

    # ---- Top consumers table -----------------------------------------------
    st.markdown('<div class="ep-card"><div class="ep-section-label">Top Consumers</div>'
                '<div class="ep-card-title">Building Ranking by Total Consumption</div></div>', unsafe_allow_html=True)
    top = buildings[["building_id", "department", "total_kwh", "total_co2e_kg", "annual_eui_kwh_m2"]].copy()
    top.columns = ["Building", "Department", "Total kWh", "CO₂e (kg)", "EUI (kWh/m²/yr)"]
    top["Total kWh"] = top["Total kWh"].map("{:,.1f}".format)
    top["CO₂e (kg)"] = top["CO₂e (kg)"].map("{:,.1f}".format)
    top["EUI (kWh/m²/yr)"] = top["EUI (kWh/m²/yr)"].map("{:.1f}".format)
    st.dataframe(top, use_container_width=True, hide_index=True)
