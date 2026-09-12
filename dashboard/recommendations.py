"""
dashboard/recommendations.py — Premium redesign with styled severity cards.
All anomaly detection logic unchanged.
"""
from __future__ import annotations
import streamlit as st
import pandas as pd
from modules.anomaly import AnomalyRecord

_RULE_LABEL = {
    "SPIKE": "Energy Spike",
    "LOW_OCC_WASTE": "Low-Occupancy Waste",
    "EUI_BREACH": "EUI Benchmark Breach",
    "ZERO_READING": "Zero / Missing Reading",
}
_RULE_ICON = {
    "SPIKE": "⚡",
    "LOW_OCC_WASTE": "💤",
    "EUI_BREACH": "📊",
    "ZERO_READING": "❓",
}
_RULE_ACTIONS = {
    "SPIKE": [
        "Inspect HVAC scheduling — verify AC was not left on during off-hours.",
        "Check for equipment left running (servers, lab instruments, lighting).",
        "Compare against occupancy data — if low occupancy, escalate to facilities.",
        "Review meter readings for data entry errors.",
    ],
    "LOW_OCC_WASTE": [
        "Install occupancy sensors or timer switches in this building.",
        "Implement a shutdown checklist for building managers.",
        "Investigate whether HVAC is running on a fixed vs. occupancy-based schedule.",
        "Consider a Building Automation System (BAS) for automated setback.",
    ],
    "EUI_BREACH": [
        "Conduct a detailed energy audit of the building.",
        "Identify the largest end-use — compare against BEE benchmark (150 kWh/m²/yr).",
        "Prioritise LED lighting retrofit if not yet completed.",
        "Upgrade to 5-star BEE-rated inverter AC on next replacement cycle.",
        "Consider rooftop solar to offset consumption.",
    ],
    "ZERO_READING": [
        "Verify the meter reading — possible meter fault or missed data submission.",
        "Check with facilities management for any planned outages.",
        "Re-enter the correct reading for the affected month.",
    ],
}


def render(df, anomalies: list[AnomalyRecord]):
    st.markdown("""
    <div class="ep-page-header">
        <div class="ep-page-title">Anomalies & Recommendations</div>
        <div class="ep-page-subtitle">
            All anomalies detected by deterministic Python rules — no AI involved in detection
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not anomalies:
        st.success("✅ No anomalies detected in the current dataset. All buildings within normal parameters.")
        return

    high = [a for a in anomalies if a.severity == "HIGH"]
    medium = [a for a in anomalies if a.severity == "MEDIUM"]
    data_issue = [a for a in anomalies if a.severity == "DATA_ISSUE"]

    # ---- Severity summary metrics ------------------------------------------
    c1, c2, c3 = st.columns(3)
    c1.metric("🔴 HIGH Severity", len(high),
              help="Energy spike or EUI benchmark breach — needs immediate investigation")
    c2.metric("🟠 MEDIUM Severity", len(medium),
              help="Low-occupancy waste — schedule investigation")
    c3.metric("🔵 Data Issues", len(data_issue),
              help="Zero or missing meter readings — verify with facilities")

    st.markdown("<br>", unsafe_allow_html=True)

    # ---- Anomaly cards by severity -----------------------------------------
    for severity, group, header_colour in [
        ("HIGH",       high,       "#ef4444"),
        ("MEDIUM",     medium,     "#f59e0b"),
        ("DATA_ISSUE", data_issue, "#3b82f6"),
    ]:
        if not group:
            continue

        st.markdown(
            f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">'
            f'<span class="ep-severity-badge ep-severity-{severity}">'
            f'{severity.replace("_", " ")}'
            f'</span>'
            f'<span style="color:#94a3b8;font-size:13px;">{len(group)} anomaly/anomalies</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

        for anomaly in group:
            rule_label = _RULE_LABEL.get(anomaly.rule, anomaly.rule)
            rule_icon  = _RULE_ICON.get(anomaly.rule, "⚠️")
            actions    = _RULE_ACTIONS.get(anomaly.rule, [])

            # Evidence dict (rendered inline)
            evidence_rows = ""
            if anomaly.extra:
                for k, v in anomaly.extra.items():
                    label = k.replace("_", " ").title()
                    if isinstance(v, float):
                        v_str = f"{v:,.2f}"
                    else:
                        v_str = str(v)
                    evidence_rows += f"<tr><td style='color:#94a3b8;padding:3px 12px 3px 0;font-size:12px;'>{label}</td><td style='color:#cbd5e1;font-size:12px;font-family:monospace;'>{v_str}</td></tr>"

            action_items = "".join(f"<li>{a}</li>" for a in actions)

            st.markdown(f"""
            <div class="ep-anomaly-card ep-anomaly-{severity}">
                <div class="ep-anomaly-header">
                    <div class="ep-anomaly-title">{rule_icon} {anomaly.building_id} &mdash; {rule_label}</div>
                    <span class="ep-severity-badge ep-severity-{severity}">{severity.replace('_',' ')}</span>
                </div>
                <div class="ep-anomaly-meta">
                    📅 Period: <strong>{anomaly.month}</strong> &nbsp;|&nbsp;
                    📏 Excess: <strong style="color:#f87171;">{anomaly.delta_kwh:,.1f} kWh</strong> above threshold
                </div>
                <div class="ep-anomaly-evidence">
                    <strong style="color:#10b981;font-size:11px;letter-spacing:0.5px;text-transform:uppercase;">
                        Detection Evidence
                    </strong><br>
                    <span style="font-size:13px;color:#cbd5e1;">{anomaly.description}</span>
                    {"<table style='margin-top:8px;'>" + evidence_rows + "</table>" if evidence_rows else ""}
                </div>
                <div style="margin-top:10px;">
                    <strong style="color:#10b981;font-size:11px;letter-spacing:0.5px;text-transform:uppercase;">
                        Recommended Actions
                    </strong>
                    <ul class="ep-action-list" style="margin-top:6px;">{action_items}</ul>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

    # ---- Full table --------------------------------------------------------
    st.markdown('<div class="ep-card"><div class="ep-section-label">All Records</div>'
                '<div class="ep-card-title">Complete Anomaly Log</div></div>', unsafe_allow_html=True)
    rows = [{
        "Building": a.building_id,
        "Month": a.month,
        "Rule": _RULE_LABEL.get(a.rule, a.rule),
        "Severity": a.severity,
        "Excess kWh": round(a.delta_kwh, 1),
        "Description": a.description[:90] + "…" if len(a.description) > 90 else a.description,
    } for a in anomalies]
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
