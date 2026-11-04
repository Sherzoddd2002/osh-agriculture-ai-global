from types import SimpleNamespace

import pytest

from backend.app.services.global_crops import normalize_crop_code, _series, _fit


def test_faostat_item_labels_map_to_supported_crop_codes():
    assert normalize_crop_code("Wheat grain") == "WHEAT"
    assert normalize_crop_code("Maize (corn)") == "MAIZE"
    assert normalize_crop_code("Rice, paddy") == "RICE"
    assert normalize_crop_code("Soya beans") == "SOYBEAN"
    assert normalize_crop_code("Potatoes") == "POTATO"


def test_global_series_uses_paired_area_and_production():
    rows = [
        SimpleNamespace(year=2020, harvested_area_ha=100, production_t=300, yield_t_ha=3),
        SimpleNamespace(year=2020, harvested_area_ha=300, production_t=600, yield_t_ha=2),
        # Area/yield-only row must not dilute a production-based denominator.
        SimpleNamespace(year=2020, harvested_area_ha=500, production_t=None, yield_t_ha=1),
    ]
    series = _series(rows)
    assert len(series) == 1
    assert series[0]["yield_t_ha"] == pytest.approx(2.25)


def test_global_model_uses_expanding_window_and_reports_baseline():
    series = [{"year": year, "yield_t_ha": 2.0 + (year - 2010) * 0.04} for year in range(2010, 2022)]
    result = _fit(series, 2026)
    assert result["training_years"] == 12
    assert result["oof_rows"] > 0
    assert result["predicted_yield_t_ha"] > 2.0
    assert result["lower_approx_t_ha"] <= result["predicted_yield_t_ha"] <= result["upper_approx_t_ha"]
