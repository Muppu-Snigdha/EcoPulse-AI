"""
test_anomaly.py
---------------
Unit tests for modules/anomaly.py
"""

from __future__ import annotations

import pandas as pd
import pytest

from modules.anomaly import detect_all, AnomalyRecord, EUI_BENCHMARK


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_row(**overrides) -> dict:
    base = {
        "month": "2023-01",
        "building_id": "Test-Bldg",
        "department": "Test",
        "kwh_consumed": 5000.0,
        "occupancy_rate": 0.80,
        "area_sqm": 1000.0,
    }
    base.update(overrides)
    return base


def _make_normal_building(n_months: int = 12) -> list[dict]:
    """Create n months of stable, normal consumption for one building."""
    rows = []
    for i in range(n_months):
        rows.append({
            "month": f"2023-{i+1:02d}",
            "building_id": "Normal-Bldg",
            "department": "Academic",
            "kwh_consumed": 5000.0 + (i % 3) * 100,  # tiny seasonal noise
            "occupancy_rate": 0.80,
            "area_sqm": 2000.0,
        })
    return rows


# ---------------------------------------------------------------------------
# ZERO_READING rule
# ---------------------------------------------------------------------------

class TestZeroReadingRule:

    def test_zero_kwh_flagged_as_data_issue(self):
        df = pd.DataFrame([_base_row(kwh_consumed=0.0)])
        records = detect_all(df)
        zero_records = [r for r in records if r.rule == "ZERO_READING"]
        assert len(zero_records) == 1
        assert zero_records[0].severity == "DATA_ISSUE"
        assert zero_records[0].building_id == "Test-Bldg"

    def test_positive_kwh_not_flagged_as_zero(self):
        df = pd.DataFrame([_base_row(kwh_consumed=1.0)])
        records = [r for r in detect_all(df) if r.rule == "ZERO_READING"]
        assert records == []

    def test_multiple_zero_rows_each_flagged(self):
        rows = [
            _base_row(month="2023-01", kwh_consumed=0.0),
            _base_row(month="2023-02", kwh_consumed=5000.0),
            _base_row(month="2023-03", kwh_consumed=0.0),
        ]
        df = pd.DataFrame(rows)
        zero_records = [r for r in detect_all(df) if r.rule == "ZERO_READING"]
        assert len(zero_records) == 2


# ---------------------------------------------------------------------------
# SPIKE rule
# ---------------------------------------------------------------------------

class TestSpikeRule:

    def test_spike_detected_on_anomaly_building(self):
        """EE-Block July anomaly from the synthetic dataset."""
        from modules.data_loader import load_csv
        df, _ = load_csv("data/raw/campus_energy.csv")
        ee_df = df[df["building_id"] == "EE-Block"]
        records = detect_all(ee_df)
        spike_records = [r for r in records if r.rule == "SPIKE"]
        assert len(spike_records) >= 1
        assert spike_records[0].month == "2023-07"
        assert spike_records[0].severity == "HIGH"
        assert spike_records[0].delta_kwh > 0

    def test_normal_building_no_spike(self):
        df = pd.DataFrame(_make_normal_building(12))
        records = [r for r in detect_all(df) if r.rule == "SPIKE"]
        assert records == []

    def test_spike_record_has_extra_metadata(self):
        from modules.data_loader import load_csv
        df, _ = load_csv("data/raw/campus_energy.csv")
        ee_df = df[df["building_id"] == "EE-Block"]
        spike = next(r for r in detect_all(ee_df) if r.rule == "SPIKE")
        assert "building_mean" in spike.extra
        assert "threshold_kwh" in spike.extra

    def test_single_row_building_no_spike(self):
        """A building with one data point has no std — should not be flagged."""
        df = pd.DataFrame([_base_row()])
        spike_records = [r for r in detect_all(df) if r.rule == "SPIKE"]
        assert spike_records == []


# ---------------------------------------------------------------------------
# LOW_OCC_WASTE rule
# ---------------------------------------------------------------------------

class TestLowOccupancyWasteRule:

    def test_low_occupancy_with_high_kwh_flagged(self):
        # 12 months of normal consumption + 1 month with low occupancy & high kWh
        rows = _make_normal_building(12)
        rows.append({
            "month": "2023-07",
            "building_id": "Normal-Bldg",
            "department": "Academic",
            "kwh_consumed": 9000.0,   # well above mean ~5100
            "occupancy_rate": 0.05,   # below 0.20 threshold
            "area_sqm": 2000.0,
        })
        df = pd.DataFrame(rows)
        low_occ = [r for r in detect_all(df) if r.rule == "LOW_OCC_WASTE"]
        assert len(low_occ) >= 1
        assert low_occ[0].severity == "MEDIUM"

    def test_low_occupancy_with_low_kwh_not_flagged(self):
        rows = _make_normal_building(12)
        rows.append({
            "month": "2023-07",
            "building_id": "Normal-Bldg",
            "department": "Academic",
            "kwh_consumed": 1000.0,   # below mean — not wasteful
            "occupancy_rate": 0.05,
            "area_sqm": 2000.0,
        })
        df = pd.DataFrame(rows)
        low_occ = [r for r in detect_all(df) if r.rule == "LOW_OCC_WASTE"]
        assert low_occ == []

    def test_high_occupancy_with_high_kwh_not_flagged_by_this_rule(self):
        rows = _make_normal_building(12)
        rows.append({
            "month": "2023-07",
            "building_id": "Normal-Bldg",
            "department": "Academic",
            "kwh_consumed": 9000.0,
            "occupancy_rate": 0.90,   # high occupancy — not this rule
            "area_sqm": 2000.0,
        })
        df = pd.DataFrame(rows)
        low_occ = [r for r in detect_all(df) if r.rule == "LOW_OCC_WASTE"]
        assert low_occ == []

    def test_anomaly_record_includes_occupancy_metadata(self):
        rows = _make_normal_building(12)
        rows.append({
            "month": "2023-12",
            "building_id": "Normal-Bldg",
            "department": "Academic",
            "kwh_consumed": 8000.0,
            "occupancy_rate": 0.10,
            "area_sqm": 2000.0,
        })
        df = pd.DataFrame(rows)
        low_occ = [r for r in detect_all(df) if r.rule == "LOW_OCC_WASTE"]
        assert len(low_occ) >= 1
        assert "occupancy_rate" in low_occ[0].extra


# ---------------------------------------------------------------------------
# EUI_BREACH rule
# ---------------------------------------------------------------------------

class TestEuiBreachRule:

    def test_high_eui_building_flagged(self):
        # EUI = 300 kWh/m2/year (double the benchmark of 150)
        # 300 kWh/m2 * 100 m2 / 12 months = 2500 kWh/month
        rows = []
        for i in range(12):
            rows.append({
                "month": f"2023-{i+1:02d}",
                "building_id": "Hot-Bldg",
                "department": "Academic",
                "kwh_consumed": 2500.0,
                "occupancy_rate": 0.8,
                "area_sqm": 100.0,
            })
        df = pd.DataFrame(rows)
        eui_records = [r for r in detect_all(df) if r.rule == "EUI_BREACH"]
        assert len(eui_records) == 1
        assert eui_records[0].severity == "HIGH"
        assert eui_records[0].extra["eui_kwh_m2"] == pytest.approx(300.0)

    def test_low_eui_building_not_flagged(self):
        # EUI = 60 kWh/m2/year (well under benchmark)
        rows = []
        for i in range(12):
            rows.append({
                "month": f"2023-{i+1:02d}",
                "building_id": "Cool-Bldg",
                "department": "Academic",
                "kwh_consumed": 500.0,   # 500 * 12 / 1000 m2 = 6 kWh/m2
                "occupancy_rate": 0.8,
                "area_sqm": 1000.0,
            })
        df = pd.DataFrame(rows)
        eui_records = [r for r in detect_all(df) if r.rule == "EUI_BREACH"]
        assert eui_records == []

    def test_eui_breach_uses_benchmark_constant(self):
        assert EUI_BENCHMARK == 150.0

    def test_eui_record_has_extra_metadata(self):
        rows = []
        for i in range(12):
            rows.append({
                "month": f"2023-{i+1:02d}",
                "building_id": "Test",
                "department": "Dept",
                "kwh_consumed": 3000.0,
                "occupancy_rate": 0.8,
                "area_sqm": 100.0,
            })
        df = pd.DataFrame(rows)
        eui_records = [r for r in detect_all(df) if r.rule == "EUI_BREACH"]
        assert len(eui_records) == 1
        extra = eui_records[0].extra
        assert "eui_kwh_m2" in extra
        assert "benchmark_kwh_m2" in extra
        assert "area_sqm" in extra


# ---------------------------------------------------------------------------
# Integration: full synthetic dataset
# ---------------------------------------------------------------------------

class TestIntegrationWithSyntheticData:

    def test_detect_all_on_synthetic_dataset(self):
        from modules.data_loader import load_csv
        df, _ = load_csv("data/raw/campus_energy.csv")
        records = detect_all(df)
        # Must detect at least the injected EE-Block spike
        spike_july = [
            r for r in records
            if r.rule == "SPIKE" and r.building_id == "EE-Block" and r.month == "2023-07"
        ]
        assert len(spike_july) == 1

    def test_detect_all_returns_list_of_anomaly_records(self):
        from modules.data_loader import load_csv
        df, _ = load_csv("data/raw/campus_energy.csv")
        records = detect_all(df)
        assert isinstance(records, list)
        for r in records:
            assert isinstance(r, AnomalyRecord)

    def test_anomaly_records_have_all_fields(self):
        from modules.data_loader import load_csv
        df, _ = load_csv("data/raw/campus_energy.csv")
        records = detect_all(df)
        for r in records:
            assert r.building_id
            assert r.month
            assert r.rule
            assert r.severity in {"HIGH", "MEDIUM", "DATA_ISSUE"}
            assert isinstance(r.delta_kwh, float)
            assert r.description
