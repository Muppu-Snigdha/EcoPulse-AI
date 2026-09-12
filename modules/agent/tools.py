"""
tools.py
--------
Tool definitions callable by the Gemini function-calling agent.

Each tool is a plain Python function that reads from the DataFrame singleton
held in `_state`. State is set once at app startup via `initialise(df)`.

All numerical results come from deterministic calculator.py / anomaly.py calls —
the LLM never generates numbers, it only calls these tools and formats the results.

Tools
-----
get_energy_summary()         -> monthly kWh + CO2e totals for the full dataset
get_building_breakdown()     -> per-building kWh, CO2e, EUI
get_carbon_footprint()       -> total campus CO2e, with budget-gap option
get_anomalies()              -> all detected anomalies (optionally filtered)
get_recommendations(topic)   -> RAG retrieval for energy efficiency advice
compare_to_benchmark()       -> campus EUI vs BEE/IEA benchmark

Public API
----------
initialise(df)               -> register the DataFrame singleton
TOOL_FUNCTIONS               -> dict[str, callable] — dispatch table for the agent loop
GEMINI_TOOL_SCHEMAS          -> list of Tool objects for Gemini function-calling registration
"""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
from google.genai import types as genai_types

from modules.calculator import (
    calc_monthly_totals,
    calc_building_totals,
    calc_carbon,
    calc_carbon_budget_gap,
    CONSTANTS,
)
from modules.anomaly import detect_all
from modules.rag.retriever import get_context_with_metadata

# ---------------------------------------------------------------------------
# State — set once at startup, read-only for all tools
# ---------------------------------------------------------------------------
_df: pd.DataFrame | None = None


def initialise(df: pd.DataFrame) -> None:
    """Register the validated DataFrame. Must be called before any tool."""
    global _df
    _df = df.copy()


def _get_df() -> pd.DataFrame:
    if _df is None:
        raise RuntimeError(
            "Tools not initialised. Call tools.initialise(df) at app startup."
        )
    return _df


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def get_energy_summary() -> dict:
    """
    Return monthly total kWh and CO2e for the entire campus.
    Sorted by month ascending.
    """
    df = _get_df()
    totals = calc_monthly_totals(df)
    return {
        "monthly_totals": totals.to_dict(orient="records"),
        "annual_total_kwh": round(float(totals["total_kwh"].sum()), 2),
        "annual_total_co2e_kg": round(float(totals["total_co2e_kg"].sum()), 2),
        "emission_factor_used": CONSTANTS["grid_emission_factor_kg_per_kwh"],
        "source": "calculator.calc_monthly_totals + India CEA 2023 emission factor",
    }


def get_building_breakdown() -> dict:
    """
    Return per-building total kWh, CO2e, floor area, and annualised EUI.
    Sorted by total kWh descending (highest consumer first).
    """
    df = _get_df()
    bldg = calc_building_totals(df)
    return {
        "buildings": bldg.to_dict(orient="records"),
        "benchmark_eui_kwh_m2_year": CONSTANTS["eui_benchmark_kwh_m2_year"],
        "source": "calculator.calc_building_totals",
    }


def get_carbon_footprint(target_kwh: float | None = None) -> dict:
    """
    Return total campus carbon footprint for the dataset period.
    Optionally compute the carbon budget gap against a target kWh.

    Parameters
    ----------
    target_kwh : float | None
        If provided, also compute the gap between actual and target.
    """
    df = _get_df()
    total_kwh = float(df["kwh_consumed"].sum())
    total_co2e = calc_carbon(total_kwh)
    result: dict[str, Any] = {
        "total_kwh": round(total_kwh, 2),
        "total_co2e_kg": total_co2e,
        "emission_factor_kg_per_kwh": CONSTANTS["grid_emission_factor_kg_per_kwh"],
        "source": "calculator.calc_carbon — India CEA 2023",
    }
    if target_kwh is not None:
        gap_co2e = calc_carbon_budget_gap(total_kwh, float(target_kwh))
        result["target_kwh"] = round(float(target_kwh), 2)
        result["carbon_gap_kg_co2e"] = gap_co2e
        result["gap_interpretation"] = (
            "over budget" if gap_co2e > 0 else "under budget (target met)"
        )
    return result


def get_anomalies(severity: str | None = None, building_id: str | None = None) -> dict:
    """
    Return all rule-based anomalies detected in the dataset.

    Parameters
    ----------
    severity    : str | None  Filter by severity: "HIGH", "MEDIUM", "DATA_ISSUE".
    building_id : str | None  Filter to a specific building.
    """
    df = _get_df()
    records = detect_all(df)

    # Apply filters
    if severity:
        records = [r for r in records if r.severity.upper() == severity.upper()]
    if building_id:
        records = [r for r in records if r.building_id.lower() == building_id.lower()]

    serialised = [
        {
            "building_id": r.building_id,
            "month": r.month,
            "rule": r.rule,
            "severity": r.severity,
            "delta_kwh": r.delta_kwh,
            "description": r.description,
            "extra": r.extra,
        }
        for r in records
    ]

    return {
        "anomalies": serialised,
        "total_count": len(serialised),
        "high_count": sum(1 for r in records if r.severity == "HIGH"),
        "medium_count": sum(1 for r in records if r.severity == "MEDIUM"),
        "data_issue_count": sum(1 for r in records if r.severity == "DATA_ISSUE"),
        "source": "anomaly.detect_all — deterministic rule-based detection",
    }


def get_recommendations(topic: str) -> dict:
    """
    Retrieve energy efficiency recommendations from the RAG knowledge base.

    Parameters
    ----------
    topic : str  The topic to search for (e.g. "HVAC savings", "LED lighting").
    """
    if not topic or not topic.strip():
        return {
            "context": "",
            "found": False,
            "chunks": [],
            "message": "No topic provided for recommendation search.",
        }

    rag = get_context_with_metadata(topic.strip(), k=3)
    return {
        "context": rag["context_text"],
        "found": rag["found"],
        "chunks": rag["chunks"],
        "topic_queried": topic.strip(),
        "source": "RAG — ChromaDB + Gemini gemini-embedding-001",
    }


def compare_to_benchmark() -> dict:
    """
    Compare the campus average EUI to the BEE/IEA educational benchmark.
    Returns per-building status and an overall campus summary.
    """
    df = _get_df()
    bldg = calc_building_totals(df)
    benchmark = CONSTANTS["eui_benchmark_kwh_m2_year"]

    statuses = []
    for _, row in bldg.iterrows():
        eui = row["annual_eui_kwh_m2"]
        delta = round(float(eui) - benchmark, 2)
        statuses.append({
            "building_id": row["building_id"],
            "department": row["department"],
            "annual_eui_kwh_m2": float(eui),
            "benchmark_kwh_m2": benchmark,
            "delta_kwh_m2": delta,
            "status": "ABOVE benchmark" if delta > 0 else "WITHIN benchmark",
        })

    campus_eui = round(float(bldg["total_kwh"].sum()) / float(bldg["area_sqm"].sum()), 2)
    campus_delta = round(campus_eui - benchmark, 2)

    return {
        "campus_eui_kwh_m2_year": campus_eui,
        "benchmark_kwh_m2_year": benchmark,
        "campus_delta_kwh_m2": campus_delta,
        "campus_status": "ABOVE benchmark" if campus_delta > 0 else "WITHIN benchmark",
        "buildings": statuses,
        "source": "calculator.calc_building_totals vs BEE/IEA benchmark",
    }


# ---------------------------------------------------------------------------
# Dispatch table — used by agent_core to call the right function
# ---------------------------------------------------------------------------
TOOL_FUNCTIONS: dict[str, callable] = {
    "get_energy_summary": get_energy_summary,
    "get_building_breakdown": get_building_breakdown,
    "get_carbon_footprint": get_carbon_footprint,
    "get_anomalies": get_anomalies,
    "get_recommendations": get_recommendations,
    "compare_to_benchmark": compare_to_benchmark,
}


# ---------------------------------------------------------------------------
# Gemini function-calling schemas
# ---------------------------------------------------------------------------
GEMINI_TOOL_SCHEMAS = genai_types.Tool(
    function_declarations=[
        genai_types.FunctionDeclaration(
            name="get_energy_summary",
            description=(
                "Get the monthly electricity consumption (kWh) and carbon footprint (kg CO2e) "
                "for the entire campus. Returns 12 monthly totals plus annual totals. "
                "Use this for questions about overall campus energy use or total CO2 emissions."
            ),
            parameters=genai_types.Schema(type=genai_types.Type.OBJECT, properties={}),
        ),
        genai_types.FunctionDeclaration(
            name="get_building_breakdown",
            description=(
                "Get per-building electricity consumption (kWh), carbon footprint (kg CO2e), "
                "floor area (m2), and annualised Energy Use Intensity (EUI in kWh/m2/year). "
                "Use this to identify which buildings consume the most energy or have the "
                "highest EUI. Results sorted by total kWh descending."
            ),
            parameters=genai_types.Schema(type=genai_types.Type.OBJECT, properties={}),
        ),
        genai_types.FunctionDeclaration(
            name="get_carbon_footprint",
            description=(
                "Calculate the total campus carbon footprint in kg CO2e using the India CEA "
                "2023 emission factor. Optionally provide a target_kwh to compute the carbon "
                "budget gap (positive = over budget, negative = under budget)."
            ),
            parameters=genai_types.Schema(
                type=genai_types.Type.OBJECT,
                properties={
                    "target_kwh": genai_types.Schema(
                        type=genai_types.Type.NUMBER,
                        description=(
                            "Optional target consumption in kWh. If provided, returns the "
                            "carbon gap between actual and target consumption."
                        ),
                    ),
                },
            ),
        ),
        genai_types.FunctionDeclaration(
            name="get_anomalies",
            description=(
                "Run deterministic rule-based anomaly detection and return a list of "
                "flagged buildings/months. Rules: SPIKE (monthly kWh > mean+2*std), "
                "LOW_OCC_WASTE (high kWh when occupancy < 20%), "
                "EUI_BREACH (annual EUI > 150 kWh/m2), ZERO_READING (missing data). "
                "Optionally filter by severity or building_id."
            ),
            parameters=genai_types.Schema(
                type=genai_types.Type.OBJECT,
                properties={
                    "severity": genai_types.Schema(
                        type=genai_types.Type.STRING,
                        description="Filter by severity: HIGH, MEDIUM, or DATA_ISSUE.",
                    ),
                    "building_id": genai_types.Schema(
                        type=genai_types.Type.STRING,
                        description="Filter anomalies for a specific building ID.",
                    ),
                },
            ),
        ),
        genai_types.FunctionDeclaration(
            name="get_recommendations",
            description=(
                "Retrieve energy efficiency recommendations from the knowledge base using "
                "semantic search. Use for questions like 'how to reduce HVAC consumption', "
                "'what are LED lighting savings', 'solar panel payback', or 'BEE benchmarks'. "
                "Always call this when the user asks HOW to improve energy efficiency."
            ),
            parameters=genai_types.Schema(
                type=genai_types.Type.OBJECT,
                properties={
                    "topic": genai_types.Schema(
                        type=genai_types.Type.STRING,
                        description=(
                            "The energy efficiency topic to search for. "
                            "Examples: 'HVAC air conditioning savings', 'LED lighting retrofit', "
                            "'solar rooftop campus', 'carbon reduction target'."
                        ),
                    ),
                },
                required=["topic"],
            ),
        ),
        genai_types.FunctionDeclaration(
            name="compare_to_benchmark",
            description=(
                "Compare each building's annual EUI to the BEE/IEA educational building "
                "benchmark of 150 kWh/m2/year. Returns per-building status (ABOVE/WITHIN) "
                "and the campus-level EUI delta. Use this when the user asks about benchmarks, "
                "targets, or which buildings are underperforming relative to standards."
            ),
            parameters=genai_types.Schema(type=genai_types.Type.OBJECT, properties={}),
        ),
    ]
)
