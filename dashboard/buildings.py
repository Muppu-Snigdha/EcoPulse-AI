"""
dashboard/buildings.py — Premium redesign.
All calculations unchanged. Visual layer only.
"""
from __future__ import annotations
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import streamlit as st
from modules.calculator import calc_building_totals, CONSTANTS
from styles.theme import PLOTLY_DARK_LAYOUT, PLOTLY_AXIS_STYLE


def render(df, anomalies):
    # Guard: show a clean message instead of a traceback on empty / None data
    if df is None or df.empty:
        st.info("No data available. Go to **Data Input** to load or upload data.", icon="📂")
        return

    buildings = calc_building_totals(df)
    benchmark = CONSTANTS["eui_benchmark_kwh_m2_year"]

    st.markdown("""
    <div class="ep-page-header">
        <div class="ep-page-title">Building Analysis</div>
        <div class="ep-page-subtitle">
            Per-building electricity consumption, carbon footprint, and Energy Use Intensity (EUI)
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ---- Summary stats -----------------------------------------------------
    above = buildings[buildings["annual_eui_kwh_m2"] > benchmark]
    c1, c2, c3 = st.columns(3)
    c1.metric("🏢 Total Buildings", len(buildings))
    c2.metric("⚠️ Above EUI Benchmark", len(above),
              help=f"Buildings exceeding {benchmark} kWh/m²/yr BEE/IEA benchmark")
    c3.metric("📐 Campus-avg EUI",
              f"{(buildings['total_kwh'].sum() / buildings['area_sqm'].sum()):.1f} kWh/m²")

    st.markdown("<br>", unsafe_allow_html=True)

    # ---- EUI bar chart -----------------------------------------------------
    st.markdown('<div class="ep-card"><div class="ep-section-label">Performance Benchmark</div>'
                '<div class="ep-card-title">Energy Use Intensity vs BEE/IEA Standard</div>'
                '<div class="ep-card-subtitle">'
                f'Benchmark: {benchmark} kWh/m²/yr (BEE ECBC 2017 + IEA Educational Buildings)'
                '</div></div>', unsafe_allow_html=True)

    buildings["_status"] = buildings["annual_eui_kwh_m2"].apply(
        lambda x: "Above benchmark" if x > benchmark else "Within benchmark"
    )
    colour_map = {"Above benchmark": "#ef4444", "Within benchmark": "#10b981"}

    try:
        fig_eui = px.bar(
            buildings.sort_values("annual_eui_kwh_m2", ascending=True),
            x="annual_eui_kwh_m2", y="building_id",
            color="_status", color_discrete_map=colour_map,
            orientation="h",
            labels={"annual_eui_kwh_m2": "EUI (kWh/m²/yr)", "building_id": "Building", "_status": "Status"},
            text="annual_eui_kwh_m2",
            hover_data={"department": True, "area_sqm": True, "_status": False},
        )
        fig_eui.add_vline(
            x=benchmark, line_dash="dash", line_color="#f59e0b", line_width=2,
            annotation_text=f"BEE/IEA benchmark ({benchmark})",
            annotation_position="top right",
            annotation_font_color="#f59e0b",
        )
        fig_eui.update_traces(texttemplate="%{text:.1f}", textposition="outside",
                              textfont=dict(color="#cbd5e1", size=11))
        fig_eui.update_layout(
            **PLOTLY_DARK_LAYOUT,
            showlegend=True,
            legend_title_text="Status",
            height=360,
            margin=dict(t=10, b=10, l=10, r=90),
        )
        fig_eui.update_xaxes(**PLOTLY_AXIS_STYLE)
        fig_eui.update_yaxes(**PLOTLY_AXIS_STYLE)
        st.plotly_chart(fig_eui, use_container_width=True)
    except Exception as exc:
        st.warning(f"EUI bar chart could not render: {exc}")

    # ---- Heatmap -----------------------------------------------------------
    st.markdown('<div class="ep-card"><div class="ep-section-label">Consumption Matrix</div>'
                '<div class="ep-card-title">Building × Month Heatmap</div>'
                '<div class="ep-card-subtitle">Colour scale: green = low, red = high consumption</div>'
                '</div>', unsafe_allow_html=True)

    try:
        pivot = df.pivot_table(index="building_id", columns="month", values="kwh_consumed", aggfunc="sum")
        fig_heat = px.imshow(
            pivot, color_continuous_scale="RdYlGn_r", aspect="auto",
            labels={"color": "kWh"},
            text_auto=".0f",
        )
        fig_heat.update_layout(
            **PLOTLY_DARK_LAYOUT,
            xaxis=dict(title="Month", gridcolor="#1f2d3d", linecolor="#1f2d3d", tickcolor="#94a3b8"),
            yaxis=dict(title="Building", gridcolor="#1f2d3d", linecolor="#1f2d3d", tickcolor="#94a3b8"),
            coloraxis_colorbar_title="kWh",
            coloraxis_colorbar=dict(tickfont=dict(color="#94a3b8")),
            height=320,
            margin=dict(t=10, b=40, l=10, r=10),
        )
        fig_heat.update_traces(textfont=dict(size=10))
        st.plotly_chart(fig_heat, use_container_width=True)
    except Exception as exc:
        st.warning(f"Heatmap could not render: {exc}")

    # ---- Building summary table --------------------------------------------
    st.markdown('<div class="ep-card"><div class="ep-section-label">Full Data</div>'
                '<div class="ep-card-title">Building Summary Table</div></div>', unsafe_allow_html=True)
    display = buildings[["building_id", "department", "total_kwh", "total_co2e_kg",
                          "area_sqm", "annual_eui_kwh_m2", "_status"]].copy()
    display.columns = ["Building", "Department", "Total kWh", "CO₂e (kg)", "Area (m²)", "EUI (kWh/m²/yr)", "vs Benchmark"]
    display["Total kWh"] = display["Total kWh"].map("{:,.1f}".format)
    display["CO₂e (kg)"] = display["CO₂e (kg)"].map("{:,.1f}".format)
    display["EUI (kWh/m²/yr)"] = display["EUI (kWh/m²/yr)"].map("{:.1f}".format)
    st.dataframe(display, use_container_width=True, hide_index=True)
