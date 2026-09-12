"""
calculator.py
-------------
Pure deterministic functions for energy and carbon calculations.

All inputs must be pre-validated (positive kWh, positive area, etc.).
No LLM calls, no I/O, no side effects — every function is unit-testable
in isolation.

Constants
---------
CONSTANTS["grid_emission_factor_kg_per_kwh"]
    India CEA 2023 national average: 0.716 kg CO2e per kWh consumed.
    Source: Central Electricity Authority, CO2 Baseline Database for
    the Indian Power Sector, 2023.

CONSTANTS["eui_benchmark_kwh_m2_year"]
    BEE / IEA benchmark for educational buildings in India: 150 kWh/m2/year.
    Buildings exceeding this are flagged as anomalies.
"""

from __future__ import annotations

import pandas as pd

# ---------------------------------------------------------------------------
# All magic numbers live here — nowhere else in the codebase.
# ---------------------------------------------------------------------------
CONSTANTS: dict = {
    "grid_emission_factor_kg_per_kwh": 0.716,   # India CEA 2023 average
    "eui_benchmark_kwh_m2_year": 150.0,          # BEE/IEA educational benchmark
    "months_per_year": 12,
}


# ---------------------------------------------------------------------------
# Scalar functions
# ---------------------------------------------------------------------------

def calc_carbon(kwh: float, grid_ef: float | None = None) -> float:
    """
    Convert kWh to kg CO2 equivalent.

    Parameters
    ----------
    kwh     : float  Energy consumed in kWh (must be >= 0).
    grid_ef : float | None  Emission factor in kg CO2e/kWh.
                            Defaults to CONSTANTS value.

    Returns
    -------
    float  Carbon footprint in kg CO2e.
    """
    if kwh < 0:
        raise ValueError(f"kwh must be >= 0, got {kwh}")
    ef = grid_ef if grid_ef is not None else CONSTANTS["grid_emission_factor_kg_per_kwh"]
    if ef <= 0:
        raise ValueError(f"grid_ef must be > 0, got {ef}")
    return round(kwh * ef, 4)


def calc_eui(kwh: float, area_sqm: float) -> float:
    """
    Calculate Energy Use Intensity (kWh per square metre).

    Parameters
    ----------
    kwh      : float  Energy consumed in kWh for the period.
    area_sqm : float  Gross floor area in square metres (must be > 0).

    Returns
    -------
    float  EUI in kWh/m2.
    """
    if area_sqm <= 0:
        raise ValueError(f"area_sqm must be > 0, got {area_sqm}")
    if kwh < 0:
        raise ValueError(f"kwh must be >= 0, got {kwh}")
    return round(kwh / area_sqm, 4)


def calc_carbon_budget_gap(actual_kwh: float, target_kwh: float,
                            grid_ef: float | None = None) -> float:
    """
    Calculate the carbon gap between actual and target consumption.

    A positive result means the building is over target (carbon excess).
    A negative result means the building is under target (carbon saving).

    Returns
    -------
    float  Gap in kg CO2e.  Positive = over budget.
    """
    ef = grid_ef if grid_ef is not None else CONSTANTS["grid_emission_factor_kg_per_kwh"]
    return round((actual_kwh - target_kwh) * ef, 4)


# ---------------------------------------------------------------------------
# DataFrame-level aggregation functions
# ---------------------------------------------------------------------------

def calc_monthly_totals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate total kWh and CO2e by month across all buildings.

    Parameters
    ----------
    df : pd.DataFrame  Must have columns: month, kwh_consumed.

    Returns
    -------
    pd.DataFrame with columns: month, total_kwh, total_co2e_kg
    Sorted by month ascending.
    """
    _require_columns(df, ["month", "kwh_consumed"])
    grouped = (
        df.groupby("month", sort=True)["kwh_consumed"]
        .sum()
        .reset_index()
        .rename(columns={"kwh_consumed": "total_kwh"})
    )
    ef = CONSTANTS["grid_emission_factor_kg_per_kwh"]
    grouped["total_co2e_kg"] = (grouped["total_kwh"] * ef).round(2)
    grouped["total_kwh"] = grouped["total_kwh"].round(2)
    return grouped


def calc_building_totals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate total kWh, CO2e, and annualised EUI per building.

    Parameters
    ----------
    df : pd.DataFrame  Must have columns: building_id, department,
                       kwh_consumed, area_sqm.

    Returns
    -------
    pd.DataFrame with columns:
        building_id, department, total_kwh, total_co2e_kg,
        area_sqm, annual_eui_kwh_m2
    Sorted by total_kwh descending.
    """
    _require_columns(df, ["building_id", "department", "kwh_consumed", "area_sqm"])
    grouped = (
        df.groupby(["building_id", "department", "area_sqm"], sort=False)
        ["kwh_consumed"]
        .sum()
        .reset_index()
        .rename(columns={"kwh_consumed": "total_kwh"})
    )
    ef = CONSTANTS["grid_emission_factor_kg_per_kwh"]
    grouped["total_co2e_kg"] = (grouped["total_kwh"] * ef).round(2)
    grouped["annual_eui_kwh_m2"] = (grouped["total_kwh"] / grouped["area_sqm"]).round(2)
    grouped["total_kwh"] = grouped["total_kwh"].round(2)
    grouped.sort_values("total_kwh", ascending=False, inplace=True, ignore_index=True)
    return grouped


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _require_columns(df: pd.DataFrame, cols: list[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")
