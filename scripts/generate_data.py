"""
generate_data.py
----------------
One-time script that produces a reproducible, synthetic campus energy CSV at
data/raw/campus_energy.csv.

Schema
------
month         : str   YYYY-MM  (12 months: 2023-01 … 2023-12)
building_id   : str   e.g. "CSE-Block"
department    : str   e.g. "Computer Science"
kwh_consumed  : float Monthly electricity consumption (kWh)
occupancy_rate: float Fraction [0, 1] of building capacity in use
area_sqm      : float Gross floor area in square metres (static per building)

Design choices
--------------
* NumPy random seed=42 → fully reproducible.
* Seasonal variation: AC load peaks in May–July (Indian summer).
* One deliberate anomaly: "EE-Block" in July 2023 consumes ~3× its normal
  kWh while occupancy is low — used to exercise the spike + low-occupancy
  anomaly rules in anomaly.py.
* Occupancy drops in May–June (summer break) and December (winter break).
"""

from __future__ import annotations

import os
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Building catalogue (static characteristics)
# ---------------------------------------------------------------------------
BUILDINGS: list[dict] = [
    {"building_id": "CSE-Block",     "department": "Computer Science",  "area_sqm": 3200},
    {"building_id": "EE-Block",      "department": "Electrical Eng.",   "area_sqm": 2800},
    {"building_id": "Main-Library",  "department": "Library",           "area_sqm": 4100},
    {"building_id": "Admin-Block",   "department": "Administration",    "area_sqm": 1800},
    {"building_id": "Boys-Hostel",   "department": "Hostel",            "area_sqm": 5500},
    {"building_id": "Girls-Hostel",  "department": "Hostel",            "area_sqm": 4800},
    {"building_id": "Canteen",       "department": "Catering",          "area_sqm":  900},
    {"building_id": "Sports-Block",  "department": "Sports & PE",       "area_sqm": 2100},
]

# Base monthly kWh per building (approximate annual / 12)
BASE_KWH: dict[str, float] = {
    "CSE-Block":    8_500,
    "EE-Block":     7_200,
    "Main-Library": 6_000,
    "Admin-Block":  3_800,
    "Boys-Hostel":  11_000,
    "Girls-Hostel":  9_500,
    "Canteen":       4_200,
    "Sports-Block":  3_100,
}

# ---------------------------------------------------------------------------
# Seasonal multipliers (Jan … Dec)
# Higher in Apr–Jul (summer AC), lower in Dec–Jan.
# ---------------------------------------------------------------------------
SEASONAL: list[float] = [
    0.85,  # Jan — mild winter
    0.90,  # Feb
    1.00,  # Mar — spring baseline
    1.15,  # Apr — warming up
    1.30,  # May — summer break, but ACs run hard
    1.35,  # Jun — peak summer
    1.25,  # Jul — monsoon relief, still warm
    1.05,  # Aug
    1.00,  # Sep — post-monsoon baseline
    0.95,  # Oct
    0.90,  # Nov
    0.80,  # Dec — winter, low occupancy
]

# Occupancy drops during summer break (May–Jun) and winter break (Dec).
OCCUPANCY_BASE: list[float] = [
    0.85, 0.88, 0.90, 0.85,
    0.40, 0.35,  # summer break
    0.88, 0.90, 0.90, 0.88, 0.86,
    0.45,        # winter break
]


def _generate_rows(rng: np.random.Generator) -> list[dict]:
    rows = []
    months = [f"2023-{m:02d}" for m in range(1, 13)]

    for bldg in BUILDINGS:
        bid = bldg["building_id"]
        base = BASE_KWH[bid]

        for idx, month in enumerate(months):
            season_mult = SEASONAL[idx]
            occ = float(np.clip(OCCUPANCY_BASE[idx] + rng.normal(0, 0.03), 0.05, 1.0))

            # Noise: ±8 % around seasonal base
            noise = rng.uniform(0.92, 1.08)
            kwh = round(base * season_mult * noise, 2)

            rows.append(
                {
                    "month": month,
                    "building_id": bid,
                    "department": bldg["department"],
                    "kwh_consumed": kwh,
                    "occupancy_rate": round(occ, 3),
                    "area_sqm": bldg["area_sqm"],
                }
            )

    return rows


def _inject_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Deliberate anomaly: EE-Block in July 2023 consumes ~3× normal while
    occupancy is very low.  This exercises both the spike rule and the
    low-occupancy-waste rule in anomaly.py.
    """
    mask = (df["building_id"] == "EE-Block") & (df["month"] == "2023-07")
    df.loc[mask, "kwh_consumed"] = round(BASE_KWH["EE-Block"] * 3.1, 2)
    df.loc[mask, "occupancy_rate"] = 0.08
    return df


def generate(output_path: str = "data/raw/campus_energy.csv") -> pd.DataFrame:
    rng = np.random.default_rng(seed=42)
    rows = _generate_rows(rng)
    df = pd.DataFrame(rows)
    df = _inject_anomalies(df)
    df.sort_values(["month", "building_id"], inplace=True, ignore_index=True)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"Generated {len(df)} rows -> {output_path}")
    return df


if __name__ == "__main__":
    generate()
