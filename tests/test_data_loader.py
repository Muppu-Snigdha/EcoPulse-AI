"""
test_data_loader.py
-------------------
Unit tests for modules/data_loader.py
"""

from __future__ import annotations

import io
import textwrap

import pandas as pd
import pytest

from modules.data_loader import load_csv, validate_dataframe, REQUIRED_COLUMNS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_df(**overrides) -> pd.DataFrame:
    """Return a minimal valid single-row DataFrame, with optional overrides."""
    base = {
        "month": "2023-01",
        "building_id": "CSE-Block",
        "department": "Computer Science",
        "kwh_consumed": 8500.0,
        "occupancy_rate": 0.85,
        "area_sqm": 3200.0,
    }
    base.update(overrides)
    return pd.DataFrame([base])


def _make_valid_df(n: int = 3) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append({
            "month": f"2023-{i+1:02d}",
            "building_id": "Test-Building",
            "department": "Test",
            "kwh_consumed": 5000.0 + i * 100,
            "occupancy_rate": 0.7,
            "area_sqm": 1000.0,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestSchemaValidation:

    def test_valid_dataframe_passes(self):
        df = _make_valid_df(12)
        clean, report = validate_dataframe(df)
        assert report["ok"] is True
        assert report["errors"] == []
        assert len(clean) == 12

    def test_missing_single_column_is_fatal(self):
        df = _make_valid_df(3).drop(columns=["kwh_consumed"])
        clean, report = validate_dataframe(df)
        assert report["ok"] is False
        assert any("kwh_consumed" in e for e in report["errors"])

    def test_missing_multiple_columns_is_fatal(self):
        df = _make_valid_df(3).drop(columns=["building_id", "area_sqm"])
        clean, report = validate_dataframe(df)
        assert report["ok"] is False

    def test_extra_columns_are_silently_dropped(self):
        df = _make_valid_df(2)
        df["extra_col"] = "noise"
        clean, report = validate_dataframe(df)
        assert "extra_col" not in clean.columns
        assert report["ok"] is True

    def test_all_required_columns_present_in_output(self):
        df = _make_valid_df(5)
        clean, _ = validate_dataframe(df)
        for col in REQUIRED_COLUMNS:
            assert col in clean.columns


# ---------------------------------------------------------------------------
# Null / NaN handling
# ---------------------------------------------------------------------------

class TestNullHandling:

    def test_null_kwh_row_dropped_with_warning(self):
        df = _make_valid_df(3)
        df.loc[1, "kwh_consumed"] = float("nan")
        clean, report = validate_dataframe(df)
        assert len(clean) == 2
        assert any("null" in w.lower() for w in report["warnings"])

    def test_null_building_id_row_dropped(self):
        df = _make_valid_df(3)
        df.loc[0, "building_id"] = None
        clean, report = validate_dataframe(df)
        assert len(clean) == 2
        assert report["ok"] is True

    def test_all_null_rows_produces_error(self):
        df = _make_valid_df(2)
        df["kwh_consumed"] = float("nan")
        clean, report = validate_dataframe(df)
        assert report["ok"] is False


# ---------------------------------------------------------------------------
# Range validation
# ---------------------------------------------------------------------------

class TestRangeValidation:

    def test_zero_kwh_row_dropped(self):
        df = _make_valid_df(3)
        df.loc[0, "kwh_consumed"] = 0.0
        clean, report = validate_dataframe(df)
        assert len(clean) == 2
        assert any("kwh_consumed" in w and "<= 0" in w for w in report["warnings"])

    def test_negative_kwh_row_dropped(self):
        df = _make_df(kwh_consumed=-100.0)
        clean, report = validate_dataframe(df)
        assert len(clean) == 0
        assert report["ok"] is False  # all rows dropped

    def test_occupancy_above_one_row_dropped(self):
        df = _make_df(occupancy_rate=1.5)
        clean, report = validate_dataframe(df)
        assert len(clean) == 0

    def test_occupancy_below_zero_row_dropped(self):
        df = _make_df(occupancy_rate=-0.1)
        clean, report = validate_dataframe(df)
        assert len(clean) == 0

    def test_zero_area_row_dropped(self):
        df = _make_df(area_sqm=0.0)
        clean, report = validate_dataframe(df)
        assert len(clean) == 0

    def test_valid_boundary_occupancy_passes(self):
        df_low = _make_df(occupancy_rate=0.0)   # exactly 0 is valid
        df_high = _make_df(occupancy_rate=1.0)  # exactly 1 is valid
        clean_low, r_low = validate_dataframe(df_low)
        clean_high, r_high = validate_dataframe(df_high)
        assert len(clean_low) == 1
        assert len(clean_high) == 1


# ---------------------------------------------------------------------------
# Row and report counts
# ---------------------------------------------------------------------------

class TestReportCounts:

    def test_rows_in_and_out_are_correct(self):
        df = _make_valid_df(10)
        # Inject 2 bad rows
        df.loc[0, "kwh_consumed"] = 0.0
        df.loc[5, "kwh_consumed"] = float("nan")
        clean, report = validate_dataframe(df)
        assert report["rows_in"] == 10
        assert report["rows_out"] == 8

    def test_clean_dataframe_index_is_reset(self):
        df = _make_valid_df(5)
        df.loc[2, "kwh_consumed"] = float("nan")
        clean, _ = validate_dataframe(df)
        assert list(clean.index) == list(range(len(clean)))


# ---------------------------------------------------------------------------
# load_csv integration
# ---------------------------------------------------------------------------

class TestLoadCsv:

    def test_loads_synthetic_dataset(self):
        """Smoke test: the real generated CSV must load cleanly."""
        clean, report = load_csv("data/raw/campus_energy.csv")
        assert report["ok"] is True
        assert len(clean) == 96
        assert report["errors"] == []

    def test_nonexistent_file_raises_value_error(self):
        with pytest.raises(ValueError, match="Cannot read CSV"):
            load_csv("data/raw/does_not_exist.csv")

    def test_non_numeric_kwh_column_coerced_or_dropped(self, tmp_path):
        csv_content = textwrap.dedent("""\
            month,building_id,department,kwh_consumed,occupancy_rate,area_sqm
            2023-01,BLD-A,Dept,8500,0.85,3200
            2023-02,BLD-A,Dept,BROKEN,0.80,3200
            2023-03,BLD-A,Dept,7200,0.82,3200
        """)
        p = tmp_path / "test.csv"
        p.write_text(csv_content)
        clean, report = load_csv(str(p))
        assert len(clean) == 2
        assert any("coerced" in w.lower() or "null" in w.lower() for w in report["warnings"])
