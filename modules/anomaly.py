"""
anomaly.py
----------
Deterministic rule-based anomaly detection for campus energy data.

Rules
-----
1. SPIKE          Monthly kWh > mean + 2*std for that building   -> HIGH
2. LOW_OCC_WASTE  kWh above building mean while occupancy < 0.2  -> MEDIUM
3. EUI_BREACH     Annualised EUI > benchmark (150 kWh/m2/year)   -> HIGH
4. ZERO_READING   kwh_consumed == 0 for any row                  -> DATA_ISSUE

Public API
----------
detect_all(df) -> list[AnomalyRecord]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import pandas as pd

from modules.calculator import CONSTANTS

# ---------------------------------------------------------------------------
SeverityLevel = Literal["HIGH", "MEDIUM", "DATA_ISSUE"]

EUI_BENCHMARK: float = CONSTANTS["eui_benchmark_kwh_m2_year"]
LOW_OCCUPANCY_THRESHOLD: float = 0.20
SPIKE_STD_MULTIPLIER: float = 2.0


@dataclass
class AnomalyRecord:
    building_id: str
    month: str              # YYYY-MM or "annual" for EUI_BREACH
    rule: str
    severity: SeverityLevel
    delta_kwh: float        # how much above the threshold / mean
    description: str        # human-readable explanation
    extra: dict = field(default_factory=dict)   # rule-specific metadata


def detect_all(df: pd.DataFrame) -> list[AnomalyRecord]:
    """
    Run all anomaly rules against the cleaned campus energy DataFrame.

    Parameters
    ----------
    df : pd.DataFrame  Output of data_loader.validate_dataframe —
                       must have columns: building_id, month,
                       kwh_consumed, occupancy_rate, area_sqm.

    Returns
    -------
    list[AnomalyRecord]  May be empty if no anomalies detected.
    """
    _require_columns(df, ["building_id", "month", "kwh_consumed",
                          "occupancy_rate", "area_sqm"])
    records: list[AnomalyRecord] = []
    records.extend(_rule_zero_reading(df))
    records.extend(_rule_spike(df))
    records.extend(_rule_low_occupancy_waste(df))
    records.extend(_rule_eui_breach(df))
    return records


# ---------------------------------------------------------------------------
# Rule implementations
# ---------------------------------------------------------------------------

def _rule_zero_reading(df: pd.DataFrame) -> list[AnomalyRecord]:
    """Flag any row where kWh is exactly zero."""
    mask = df["kwh_consumed"] == 0.0
    records = []
    for _, row in df[mask].iterrows():
        records.append(
            AnomalyRecord(
                building_id=row["building_id"],
                month=row["month"],
                rule="ZERO_READING",
                severity="DATA_ISSUE",
                delta_kwh=0.0,
                description=(
                    f"{row['building_id']} reported 0 kWh for {row['month']}. "
                    "Possible meter fault or missing data."
                ),
            )
        )
    return records


def _rule_spike(df: pd.DataFrame) -> list[AnomalyRecord]:
    """
    Flag monthly kWh that exceeds mean + SPIKE_STD_MULTIPLIER * std
    for each building individually.
    """
    records = []
    stats = (
        df.groupby("building_id")["kwh_consumed"]
        .agg(["mean", "std"])
        .reset_index()
        .rename(columns={"mean": "bldg_mean", "std": "bldg_std"})
    )
    merged = df.merge(stats, on="building_id")
    # Buildings with a single row have std == NaN — skip spike check for them
    merged = merged.dropna(subset=["bldg_std"])

    threshold = merged["bldg_mean"] + SPIKE_STD_MULTIPLIER * merged["bldg_std"]
    spike_mask = merged["kwh_consumed"] > threshold

    for _, row in merged[spike_mask].iterrows():
        thresh_val = round(
            row["bldg_mean"] + SPIKE_STD_MULTIPLIER * row["bldg_std"], 2
        )
        delta = round(row["kwh_consumed"] - thresh_val, 2)
        records.append(
            AnomalyRecord(
                building_id=row["building_id"],
                month=row["month"],
                rule="SPIKE",
                severity="HIGH",
                delta_kwh=delta,
                description=(
                    f"{row['building_id']} consumed {row['kwh_consumed']:.0f} kWh "
                    f"in {row['month']} — {delta:.0f} kWh above the spike threshold "
                    f"({thresh_val:.0f} kWh = mean + 2\u00d7std)."
                ),
                extra={"building_mean": round(row["bldg_mean"], 2),
                       "building_std": round(row["bldg_std"], 2),
                       "threshold_kwh": thresh_val},
            )
        )
    return records


def _rule_low_occupancy_waste(df: pd.DataFrame) -> list[AnomalyRecord]:
    """
    Flag rows where occupancy < LOW_OCCUPANCY_THRESHOLD but kWh is
    above the building's mean consumption.
    """
    records = []
    means = (
        df.groupby("building_id")["kwh_consumed"]
        .mean()
        .rename("bldg_mean")
    )
    merged = df.join(means, on="building_id")

    low_occ = merged["occupancy_rate"] < LOW_OCCUPANCY_THRESHOLD
    above_mean = merged["kwh_consumed"] > merged["bldg_mean"]
    mask = low_occ & above_mean

    for _, row in merged[mask].iterrows():
        delta = round(row["kwh_consumed"] - row["bldg_mean"], 2)
        records.append(
            AnomalyRecord(
                building_id=row["building_id"],
                month=row["month"],
                rule="LOW_OCC_WASTE",
                severity="MEDIUM",
                delta_kwh=delta,
                description=(
                    f"{row['building_id']} in {row['month']}: occupancy only "
                    f"{row['occupancy_rate']*100:.0f}% yet consumed "
                    f"{row['kwh_consumed']:.0f} kWh — "
                    f"{delta:.0f} kWh above its monthly mean."
                ),
                extra={"occupancy_rate": row["occupancy_rate"],
                       "building_mean_kwh": round(row["bldg_mean"], 2)},
            )
        )
    return records


def _rule_eui_breach(df: pd.DataFrame) -> list[AnomalyRecord]:
    """
    Flag buildings whose annualised EUI exceeds the BEE/IEA benchmark.
    EUI is computed over all available months in the dataset.
    """
    records = []
    totals = (
        df.groupby(["building_id", "area_sqm"])["kwh_consumed"]
        .sum()
        .reset_index()
    )
    # Months present — used to annualise if fewer than 12 months of data
    n_months = df["month"].nunique()

    for _, row in totals.iterrows():
        annual_kwh = row["kwh_consumed"] * (12 / n_months) if n_months < 12 else row["kwh_consumed"]
        eui = round(annual_kwh / row["area_sqm"], 2)
        if eui > EUI_BENCHMARK:
            delta = round(eui - EUI_BENCHMARK, 2)
            records.append(
                AnomalyRecord(
                    building_id=row["building_id"],
                    month="annual",
                    rule="EUI_BREACH",
                    severity="HIGH",
                    delta_kwh=round(delta * row["area_sqm"], 2),
                    description=(
                        f"{row['building_id']} annual EUI = {eui:.1f} kWh/m\u00b2 "
                        f"— {delta:.1f} kWh/m\u00b2 above the {EUI_BENCHMARK} kWh/m\u00b2 "
                        f"benchmark."
                    ),
                    extra={"eui_kwh_m2": eui,
                           "benchmark_kwh_m2": EUI_BENCHMARK,
                           "area_sqm": row["area_sqm"]},
                )
            )
    return records


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _require_columns(df: pd.DataFrame, cols: list[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"DataFrame missing required columns: {missing}")
