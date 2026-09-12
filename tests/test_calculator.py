"""
test_calculator.py
------------------
Unit tests for modules/calculator.py
"""

from __future__ import annotations

import pytest
import pandas as pd

from modules.calculator import (
    calc_carbon,
    calc_eui,
    calc_carbon_budget_gap,
    calc_monthly_totals,
    calc_building_totals,
    CONSTANTS,
)


# ---------------------------------------------------------------------------
# calc_carbon
# ---------------------------------------------------------------------------

class TestCalcCarbon:

    def test_basic_calculation(self):
        ef = CONSTANTS["grid_emission_factor_kg_per_kwh"]
        result = calc_carbon(1000.0)
        assert result == round(1000.0 * ef, 4)

    def test_zero_kwh_returns_zero(self):
        assert calc_carbon(0.0) == 0.0

    def test_custom_emission_factor(self):
        result = calc_carbon(500.0, grid_ef=0.5)
        assert result == 250.0

    def test_negative_kwh_raises(self):
        with pytest.raises(ValueError, match="kwh must be >= 0"):
            calc_carbon(-1.0)

    def test_zero_or_negative_ef_raises(self):
        with pytest.raises(ValueError, match="grid_ef must be > 0"):
            calc_carbon(100.0, grid_ef=0.0)
        with pytest.raises(ValueError, match="grid_ef must be > 0"):
            calc_carbon(100.0, grid_ef=-0.5)

    def test_result_is_rounded_to_4dp(self):
        result = calc_carbon(1.0, grid_ef=0.33333)
        assert result == round(1.0 * 0.33333, 4)

    def test_uses_india_cea_constant_by_default(self):
        # Verify the default emission factor is the India CEA 2023 value
        assert CONSTANTS["grid_emission_factor_kg_per_kwh"] == 0.716
        assert calc_carbon(1000.0) == 716.0


# ---------------------------------------------------------------------------
# calc_eui
# ---------------------------------------------------------------------------

class TestCalcEui:

    def test_basic_calculation(self):
        assert calc_eui(10000.0, 100.0) == 100.0

    def test_result_rounded_to_4dp(self):
        result = calc_eui(1000.0, 3.0)
        assert result == round(1000.0 / 3.0, 4)

    def test_zero_area_raises(self):
        with pytest.raises(ValueError, match="area_sqm must be > 0"):
            calc_eui(1000.0, 0.0)

    def test_negative_area_raises(self):
        with pytest.raises(ValueError, match="area_sqm must be > 0"):
            calc_eui(1000.0, -50.0)

    def test_negative_kwh_raises(self):
        with pytest.raises(ValueError, match="kwh must be >= 0"):
            calc_eui(-100.0, 200.0)

    def test_zero_kwh_is_valid(self):
        # A building with no consumption is valid (EUI = 0)
        assert calc_eui(0.0, 500.0) == 0.0


# ---------------------------------------------------------------------------
# calc_carbon_budget_gap
# ---------------------------------------------------------------------------

class TestCalcCarbonBudgetGap:

    def test_over_budget_is_positive(self):
        # 1200 actual vs 1000 target = 200 kWh excess
        gap = calc_carbon_budget_gap(1200.0, 1000.0, grid_ef=1.0)
        assert gap == 200.0

    def test_under_budget_is_negative(self):
        gap = calc_carbon_budget_gap(800.0, 1000.0, grid_ef=1.0)
        assert gap == -200.0

    def test_equal_actual_and_target_is_zero(self):
        gap = calc_carbon_budget_gap(1000.0, 1000.0, grid_ef=1.0)
        assert gap == 0.0

    def test_uses_default_emission_factor(self):
        ef = CONSTANTS["grid_emission_factor_kg_per_kwh"]
        gap = calc_carbon_budget_gap(1100.0, 1000.0)
        assert gap == round(100.0 * ef, 4)


# ---------------------------------------------------------------------------
# calc_monthly_totals
# ---------------------------------------------------------------------------

class TestCalcMonthlyTotals:

    def _sample_df(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"month": "2023-01", "building_id": "A", "kwh_consumed": 1000.0},
            {"month": "2023-01", "building_id": "B", "kwh_consumed": 2000.0},
            {"month": "2023-02", "building_id": "A", "kwh_consumed": 1500.0},
            {"month": "2023-02", "building_id": "B", "kwh_consumed": 2500.0},
        ])

    def test_sums_correctly_per_month(self):
        df = self._sample_df()
        result = calc_monthly_totals(df)
        assert result.loc[result["month"] == "2023-01", "total_kwh"].values[0] == 3000.0
        assert result.loc[result["month"] == "2023-02", "total_kwh"].values[0] == 4000.0

    def test_output_has_required_columns(self):
        df = self._sample_df()
        result = calc_monthly_totals(df)
        assert set(result.columns) >= {"month", "total_kwh", "total_co2e_kg"}

    def test_co2e_matches_carbon_formula(self):
        df = self._sample_df()
        result = calc_monthly_totals(df)
        ef = CONSTANTS["grid_emission_factor_kg_per_kwh"]
        jan_kwh = 3000.0
        expected_co2e = round(jan_kwh * ef, 2)
        actual = result.loc[result["month"] == "2023-01", "total_co2e_kg"].values[0]
        assert actual == expected_co2e

    def test_sorted_by_month_ascending(self):
        df = self._sample_df()
        result = calc_monthly_totals(df)
        assert list(result["month"]) == sorted(result["month"])

    def test_missing_month_column_raises(self):
        df = pd.DataFrame([{"building_id": "A", "kwh_consumed": 1000.0}])
        with pytest.raises(ValueError, match="missing required columns"):
            calc_monthly_totals(df)


# ---------------------------------------------------------------------------
# calc_building_totals
# ---------------------------------------------------------------------------

class TestCalcBuildingTotals:

    def _sample_df(self) -> pd.DataFrame:
        return pd.DataFrame([
            {"building_id": "A", "department": "D1", "kwh_consumed": 1000.0, "area_sqm": 100.0},
            {"building_id": "A", "department": "D1", "kwh_consumed": 2000.0, "area_sqm": 100.0},
            {"building_id": "B", "department": "D2", "kwh_consumed": 5000.0, "area_sqm": 200.0},
        ])

    def test_aggregates_kwh_per_building(self):
        df = self._sample_df()
        result = calc_building_totals(df)
        row_a = result[result["building_id"] == "A"].iloc[0]
        assert row_a["total_kwh"] == 3000.0

    def test_eui_calculation(self):
        df = self._sample_df()
        result = calc_building_totals(df)
        row_a = result[result["building_id"] == "A"].iloc[0]
        # 3000 kWh / 100 m2 = 30 kWh/m2
        assert row_a["annual_eui_kwh_m2"] == 30.0

    def test_sorted_by_total_kwh_descending(self):
        df = self._sample_df()
        result = calc_building_totals(df)
        kwh_values = list(result["total_kwh"])
        assert kwh_values == sorted(kwh_values, reverse=True)

    def test_output_has_required_columns(self):
        df = self._sample_df()
        result = calc_building_totals(df)
        expected = {"building_id", "department", "total_kwh", "total_co2e_kg",
                    "area_sqm", "annual_eui_kwh_m2"}
        assert expected.issubset(set(result.columns))

    def test_missing_column_raises(self):
        df = pd.DataFrame([{"building_id": "A", "kwh_consumed": 100.0}])
        with pytest.raises(ValueError, match="missing required columns"):
            calc_building_totals(df)
