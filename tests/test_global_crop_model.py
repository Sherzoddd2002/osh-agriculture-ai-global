from types import SimpleNamespace
from backend.app.services.global_crops import normalize_crop_code, _series, _fit

def test_global_crop_aliases_are_normalized():
    assert normalize_crop_code("Wheat grain") == "WHEAT"
    assert normalize_crop_code("Corn") == "MAIZE"
    assert normalize_crop_code("Paddy rice") == "RICE"

def test_global_series_uses_area_weighted_production():
    rows=[
      SimpleNamespace(year=2020,harvested_area_ha=100,production_t=300,yield_t_ha=3),
      SimpleNamespace(year=2020,harvested_area_ha=300,production_t=600,yield_t_ha=2),
    ]
    series=_series(rows)
    assert len(series)==1
    assert series[0]["yield_t_ha"]==pytest.approx(2.25)

def test_global_model_uses_expanding_window_and_reports_baseline():
    import pytest
    series=[{"year":y,"yield_t_ha":2.0+(y-2010)*0.04} for y in range(2010,2022)]
    result=_fit(series,2026)
    assert result["training_years"]==12
    assert result["oof_rows"]>0
    assert result["predicted_yield_t_ha"]>2.0
    assert result["lower_approx_t_ha"]<=result["predicted_yield_t_ha"]<=result["upper_approx_t_ha"]
