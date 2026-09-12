"""
data_loader.py
--------------
Loads, validates, and cleans the campus energy CSV (or an uploaded DataFrame).

Public API
----------
load_csv(path)            -> (pd.DataFrame, dict)
validate_dataframe(df)    -> (pd.DataFrame, dict)

The validation report dict has the shape:
  {
      "ok": bool,
      "errors": list[str],       # fatal — prevents further processing
      "warnings": list[str],     # non-fatal — rows were dropped or coerced
      "rows_in": int,
      "rows_out": int,
  }
"""

from __future__ import annotations

import pandas as pd


# ---------------------------------------------------------------------------
# Canonical required columns used internally by EcoPulse
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS: list[str] = [
    "month",
    "building_id",
    "department",
    "kwh_consumed",
    "occupancy_rate",
    "area_sqm",
]


# ---------------------------------------------------------------------------
# Column-name aliases
#
# Different real-world datasets may use different names for the same field.
# EcoPulse converts them into the canonical names above before validation.
# ---------------------------------------------------------------------------

COLUMN_ALIASES: dict[str, str] = {

    # -------------------------
    # Energy consumption
    # -------------------------
    "energy_kwh": "kwh_consumed",
    "electricity_usage": "kwh_consumed",
    "electricity_kwh": "kwh_consumed",
    "power_consumption": "kwh_consumed",
    "energy_consumption": "kwh_consumed",
    "energy_consumption_kwh": "kwh_consumed",
    "kwh": "kwh_consumed",
    "energy": "kwh_consumed",

    # -------------------------
    # Building
    # -------------------------
    "building": "building_id",
    "building_name": "building_id",
    "facility": "building_id",
    "facility_id": "building_id",
    "facility_name": "building_id",
    "block": "building_id",
    "block_name": "building_id",

    # -------------------------
    # Department
    # -------------------------
    "dept": "department",
    "unit": "department",
    "department_name": "department",
    "division": "department",

    # -------------------------
    # Month / time
    # -------------------------
    "period": "month",
    "date": "month",
    "month_year": "month",
    "billing_month": "month",
    "billing_period": "month",

    # -------------------------
    # Area
    # -------------------------
    "area_m2": "area_sqm",
    "area_sq_m": "area_sqm",
    "area_square_meters": "area_sqm",
    "floor_area": "area_sqm",
    "floor_area_m2": "area_sqm",
    "floor_area_sqm": "area_sqm",
    "building_area": "area_sqm",

    # -------------------------
    # Occupancy
    # -------------------------
    "occupancy_pct": "occupancy_rate",
    "occupancy_percent": "occupancy_rate",
    "occupancy_percentage": "occupancy_rate",
    "occupancy_rate_percent": "occupancy_rate",
    "occupancy": "occupancy_rate",
}


# ---------------------------------------------------------------------------
# Validation bounds
# ---------------------------------------------------------------------------

KWH_MIN: float = 0.0
KWH_MAX: float = 1_000_000.0

OCCUPANCY_MIN: float = 0.0
OCCUPANCY_MAX: float = 1.0

AREA_MIN: float = 1.0


# ---------------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------------

def load_csv(path: str) -> tuple[pd.DataFrame, dict]:
    """
    Read a CSV file, then validate and clean it.

    Parameters
    ----------
    path : str
        Path to the CSV file.

    Returns
    -------
    df : pd.DataFrame
        Cleaned dataframe.

    report : dict
        Validation report.

    Raises
    ------
    ValueError
        If the CSV cannot be read.
    FileNotFoundError
        If the file does not exist.
    """

    try:
        raw = pd.read_csv(path)
    except FileNotFoundError:
        raise

    except Exception as exc:
        raise ValueError(
            f"Cannot read CSV at '{path}': {exc}"
        ) from exc

    return validate_dataframe(raw)


# ---------------------------------------------------------------------------
# Column normalization
# ---------------------------------------------------------------------------

def _normalise_columns(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Convert common alternative column names into EcoPulse's canonical names.

    Example:

        energy_kwh       -> kwh_consumed
        facility         -> building_id
        unit             -> department
        period           -> month
        floor_area       -> area_sqm
        occupancy_pct    -> occupancy_rate

    The function avoids overwriting a canonical column if it already exists.

    Returns
    -------
    dataframe
    list of warning messages
    """

    df = df.copy()

    notes: list[str] = []

    # Remove accidental spaces around column names.
    df.columns = [
        str(column).strip()
        for column in df.columns
    ]

    rename_map: dict[str, str] = {}

    # Process aliases one by one.
    for alternative, canonical in COLUMN_ALIASES.items():

        # If the alternative column does not exist, nothing to do.
        if alternative not in df.columns:
            continue

        # If the canonical column already exists,
        # do not overwrite it.
        if canonical in df.columns:
            continue

        # Avoid mapping multiple alternative columns
        # to the same canonical column.
        if canonical in rename_map.values():
            continue

        rename_map[alternative] = canonical

    # Apply the mappings.
    if rename_map:

        df = df.rename(columns=rename_map)

        for alternative, canonical in rename_map.items():
            notes.append(
                f"Column '{alternative}' mapped to '{canonical}'."
            )

    return df, notes


# ---------------------------------------------------------------------------
# Main validation function
# ---------------------------------------------------------------------------

def validate_dataframe(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, dict]:
    """
    Validate and clean a DataFrame.

    Supports:
    - Default synthetic dataset
    - Canonical EcoPulse CSV
    - Uploaded CSVs using supported alternative column names

    Returns
    -------
    clean_df : pd.DataFrame
    report : dict
    """

    # -----------------------------------------------------------------------
    # Basic report
    # -----------------------------------------------------------------------

    report: dict = {
        "ok": True,
        "errors": [],
        "warnings": [],
        "rows_in": len(df),
        "rows_out": 0,
    }

    # -----------------------------------------------------------------------
    # Safety check
    # -----------------------------------------------------------------------

    if not isinstance(df, pd.DataFrame):
        report["ok"] = False
        report["errors"].append(
            "Input data must be a pandas DataFrame."
        )
        return df, report

    # -----------------------------------------------------------------------
    # 0. Normalize alternative column names
    # -----------------------------------------------------------------------

    df, rename_notes = _normalise_columns(df)

    report["warnings"].extend(rename_notes)

    # -----------------------------------------------------------------------
    # 0.1 Normalize occupancy scale
    #
    # EcoPulse internally expects:
    #
    #     0.0 = 0%
    #     0.5 = 50%
    #     1.0 = 100%
    #
    # Some uploaded datasets use:
    #
    #     0 = 0%
    #     50 = 50%
    #     100 = 100%
    #
    # Detect and convert the latter.
    # -----------------------------------------------------------------------

    if "occupancy_rate" in df.columns:

        try:

            numeric_occ = pd.to_numeric(
                df["occupancy_rate"],
                errors="coerce",
            )

            valid_values = numeric_occ.dropna()

            if not valid_values.empty:

                if valid_values.max() > 1.0:

                    df = df.copy()

                    df["occupancy_rate"] = (
                        numeric_occ / 100.0
                    )

                    report["warnings"].append(
                        "Column 'occupancy_rate' values were "
                        "greater than 1 and were divided by 100 "
                        "to convert percentage values to fractions."
                    )

        except Exception:
            # Normal dtype validation below will handle invalid values.
            pass

    # -----------------------------------------------------------------------
    # 1. Required schema check
    # -----------------------------------------------------------------------

    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing:

        report["ok"] = False

        report["errors"].append(
            f"Missing required columns: {missing}. "
            f"Expected: {REQUIRED_COLUMNS}"
        )

        report["rows_out"] = 0

        return df, report

    # -----------------------------------------------------------------------
    # Keep only the columns required by EcoPulse.
    #
    # Extra columns from external datasets are ignored safely.
    # -----------------------------------------------------------------------

    df = df[REQUIRED_COLUMNS].copy()

    # -----------------------------------------------------------------------
    # 2. Numeric dtype coercion
    # -----------------------------------------------------------------------

    numeric_columns = [
        "kwh_consumed",
        "occupancy_rate",
        "area_sqm",
    ]

    for column in numeric_columns:

        original_nulls = df[column].isna().sum()

        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

        new_nulls = (
            df[column].isna().sum()
            - original_nulls
        )

        if new_nulls > 0:

            report["warnings"].append(
                f"Column '{column}': "
                f"{new_nulls} value(s) could not be converted "
                f"to numeric and were set to NaN."
            )

    # -----------------------------------------------------------------------
    # 3. Remove rows with missing numeric values
    # -----------------------------------------------------------------------

    numeric_columns = [
        "kwh_consumed",
        "occupancy_rate",
        "area_sqm",
    ]

    null_mask = (
        df[numeric_columns]
        .isna()
        .any(axis=1)
    )

    number_of_null_rows = int(null_mask.sum())

    if number_of_null_rows > 0:

        report["warnings"].append(
            f"Dropped {number_of_null_rows} row(s) "
            "with null values in numeric columns."
        )

        df = df[~null_mask].copy()

    # -----------------------------------------------------------------------
    # 4. Remove rows with missing building/month
    # -----------------------------------------------------------------------

    string_null_mask = (
        df["building_id"].isna()
        | df["month"].isna()
    )

    number_of_string_nulls = int(
        string_null_mask.sum()
    )

    if number_of_string_nulls > 0:

        report["warnings"].append(
            f"Dropped {number_of_string_nulls} row(s) "
            "with null building_id or month."
        )

        df = df[~string_null_mask].copy()

    # -----------------------------------------------------------------------
    # 5. kWh range validation
    # -----------------------------------------------------------------------

    # Zero and negative energy values are invalid for the loader.
    # Zero readings can still be handled as anomalies if needed elsewhere,
    # but the current project validation treats <= 0 as invalid input.

    bad_kwh = (
        df["kwh_consumed"]
        <= KWH_MIN
    )

    number_of_bad_kwh = int(
        bad_kwh.sum()
    )

    if number_of_bad_kwh > 0:

        report["warnings"].append(
            f"Dropped {number_of_bad_kwh} row(s) "
            "where kwh_consumed <= 0."
        )

        df = df[~bad_kwh].copy()

    # -----------------------------------------------------------------------
    # Maximum kWh validation
    # -----------------------------------------------------------------------

    over_kwh = (
        df["kwh_consumed"]
        > KWH_MAX
    )

    number_of_over_kwh = int(
        over_kwh.sum()
    )

    if number_of_over_kwh > 0:

        report["warnings"].append(
            f"Dropped {number_of_over_kwh} row(s) "
            f"where kwh_consumed > {KWH_MAX} "
            "(likely data entry error)."
        )

        df = df[~over_kwh].copy()

    # -----------------------------------------------------------------------
    # 6. Occupancy range validation
    # -----------------------------------------------------------------------

    bad_occupancy = (
        (df["occupancy_rate"] < OCCUPANCY_MIN)
        |
        (df["occupancy_rate"] > OCCUPANCY_MAX)
    )

    number_of_bad_occupancy = int(
        bad_occupancy.sum()
    )

    if number_of_bad_occupancy > 0:

        report["warnings"].append(
            f"Dropped {number_of_bad_occupancy} row(s) "
            "where occupancy_rate was not in [0, 1]."
        )

        df = df[~bad_occupancy].copy()

    # -----------------------------------------------------------------------
    # 7. Area validation
    # -----------------------------------------------------------------------

    bad_area = (
        df["area_sqm"]
        < AREA_MIN
    )

    number_of_bad_area = int(
        bad_area.sum()
    )

    if number_of_bad_area > 0:

        report["warnings"].append(
            f"Dropped {number_of_bad_area} row(s) "
            f"where area_sqm < {AREA_MIN}."
        )

        df = df[~bad_area].copy()

    # -----------------------------------------------------------------------
    # 8. Final cleanup
    # -----------------------------------------------------------------------

    df = df.reset_index(drop=True)

    report["rows_out"] = len(df)

    # -----------------------------------------------------------------------
    # If every row was removed, return a fatal validation error.
    # -----------------------------------------------------------------------

    if len(df) == 0:

        report["ok"] = False

        report["errors"].append(
            "All rows were dropped during validation. "
            "No usable data remains."
        )

    return df, report