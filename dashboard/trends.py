"""
dashboard/trends.py — Premium redesign.
All calculations unchanged. Visual layer only.
"""
from __future__ import annotations
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from modules.calculator import calc_monthly_totals
from styles.theme import PLOTLY_DARK_LAYOUT, PLOTLY_AXIS_STYLE


def render(df, anomalies):
    # Guard: show a clean message instead of a traceback on empty / None data
    if df is None or df.empty:
        st.info("No data available. Go to **Data Input** to load or upload data.", icon="📂")
        return

    monthly_campus = calc_monthly_totals(df)

    st.markdown("""
    <div class="ep-page-header">
        <div class="ep-page-title">Monthly Energy Trends</div>
        <div class="ep-page-subtitle">Track electricity consumption and carbon footprint month by month</div>
    </div>
    """, unsafe_allow_html=True)

    # ---- Summary stat cards ------------------------------------------------
    peak_row = monthly_campus.loc[monthly_campus["total_kwh"].idxmax()]
    low_row  = monthly_campus.loc[monthly_campus["total_kwh"].idxmin()]
    avg_kwh  = monthly_campus["total_kwh"].mean()

    c1, c2, c3 = st.columns(3)
    c1.metric("📈 Peak Month", peak_row["month"], f"{peak_row['total_kwh']:,.0f} kWh")
    c2.metric("📉 Lowest Month", low_row["month"], f"{low_row['total_kwh']:,.0f} kWh")
    c3.metric("📊 Monthly Average", f"{avg_kwh:,.0f} kWh")

    st.markdown("<br>", unsafe_allow_html=True)

    # ---- Per-building line chart -------------------------------------------
    st.markdown('<div class="ep-card"><div class="ep-section-label">Building Detail</div>'
                '<div class="ep-card-title">Monthly Consumption per Building</div>'
                '<div class="ep-card-subtitle">Red ✕ markers indicate detected spike anomalies</div></div>',
                unsafe_allow_html=True)

    try:
        fig_lines = px.line(
            df, x="month", y="kwh_consumed", color="building_id", markers=True,
            labels={"kwh_consumed": "kWh", "month": "Month", "building_id": "Building"},
            color_discrete_sequence=px.colors.qualitative.Set2,
        )
        anomaly_months = {
            (a.building_id, a.month) for a in anomalies
            if a.rule == "SPIKE" and a.month != "annual"
        }
        for bldg, month in anomaly_months:
            row = df[(df["building_id"] == bldg) & (df["month"] == month)]
            if not row.empty:
                fig_lines.add_scatter(
                    x=row["month"], y=row["kwh_consumed"],
                    mode="markers",
                    marker=dict(color="#ef4444", size=14, symbol="x-thin", line=dict(width=3, color="#ef4444")),
                    name=f"⚠️ Spike: {bldg}",
                    showlegend=True,
                    hovertemplate=f"<b>{bldg}</b><br>{month}<br>SPIKE ANOMALY<extra></extra>",
                )
        fig_lines.update_layout(
            **PLOTLY_DARK_LAYOUT,
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=-0.35, bgcolor="rgba(0,0,0,0)"),
            margin=dict(t=10, b=90, l=10, r=10),
            xaxis_tickangle=-45,
            height=380,
        )
        fig_lines.update_xaxes(**PLOTLY_AXIS_STYLE)
        fig_lines.update_yaxes(**PLOTLY_AXIS_STYLE)
        st.plotly_chart(fig_lines, use_container_width=True)
    except Exception as exc:
        st.warning(f"Building trend chart could not render: {exc}")

    # ---- CO2e area chart ---------------------------------------------------
    st.markdown('<div class="ep-card"><div class="ep-section-label">Carbon Footprint</div>'
                '<div class="ep-card-title">Monthly Campus CO₂ Emissions</div></div>', unsafe_allow_html=True)
    try:
        fig_co2 = go.Figure()
        fig_co2.add_scatter(
            x=monthly_campus["month"], y=monthly_campus["total_co2e_kg"],
            fill="tozeroy",
            fillcolor="rgba(239,68,68,0.12)",
            line=dict(color="#ef4444", width=2.5),
            mode="lines+markers",
            marker=dict(size=6, color="#ef4444"),
            name="CO₂e (kg)",
            hovertemplate="<b>%{x}</b><br>%{y:,.0f} kg CO₂e<extra></extra>",
        )
        fig_co2.update_layout(
            **PLOTLY_DARK_LAYOUT,
            xaxis_tickangle=-45,
            yaxis=dict(title="kg CO₂e", gridcolor="#1f2d3d", linecolor="#1f2d3d", tickcolor="#94a3b8"),
            height=280,
            margin=dict(t=10, b=60, l=10, r=10),
        )
        fig_co2.update_xaxes(**PLOTLY_AXIS_STYLE)
        st.plotly_chart(fig_co2, use_container_width=True)
    except Exception as exc:
        st.warning(f"CO₂ emissions chart could not render: {exc}")

    # ---- Summary table -----------------------------------------------------
    st.markdown('<div class="ep-card"><div class="ep-section-label">Data</div>'
                '<div class="ep-card-title">Monthly Summary</div></div>', unsafe_allow_html=True)
    display = monthly_campus.copy()
    display.columns = ["Month", "Total kWh", "Total CO₂e (kg)"]
    display["Total kWh"] = display["Total kWh"].map("{:,.1f}".format)
    display["Total CO₂e (kg)"] = display["Total CO₂e (kg)"].map("{:,.1f}".format)
    st.dataframe(display, use_container_width=True, hide_index=True)
