from datetime import date
import pandas as pd
from backend.app.services.nasa_power import aggregate_weather, aggregate_calendar_year_weather


def test_winter_crop_window_aggregates_by_harvest_year():
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2020-10-01", "2021-01-01", "2021-06-30"]),
        "T2M": [10.0, 2.0, 25.0],
        "T2M_MAX": [15.0, 5.0, 37.0],
        "T2M_MIN": [5.0, -2.0, 14.0],
        "PRECTOTCORR": [1.0, 0.0, 2.0],
        "RH2M": [50.0, 60.0, 40.0],
        "WS2M": [2.0, 3.0, 4.0],
        "ALLSKY_SFC_SW_DWN": [10.0, 8.0, 20.0],
    })
    rows = aggregate_weather(frame, 2021, 2021, "10-01", "06-30")
    assert len(rows) == 1
    assert rows[0]["year"] == 2021
    assert rows[0]["wx_observed_days"] == 3
    assert rows[0]["wx_precip_sum_mm"] == 3.0
    assert rows[0]["wx_hot_days_ge_35c"] == 1
    assert rows[0]["wx_frost_days_lt_0c"] == 1

def test_calendar_year_climate_aggregation_without_yield_data():
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2022-01-01", "2022-06-01", "2022-12-31"]),
        "T2M": [2.0, 28.0, 1.0],
        "T2M_MAX": [7.0, 36.0, 5.0],
        "T2M_MIN": [-3.0, 18.0, -5.0],
        "PRECTOTCORR": [1.0, 2.0, 0.5],
        "RH2M": [70.0, 35.0, 75.0],
        "WS2M": [2.0, 4.0, 1.0],
        "ALLSKY_SFC_SW_DWN": [5.0, 22.0, 4.0],
    })

    rows = aggregate_calendar_year_weather(frame, 2022, 2022)

    assert len(rows) == 1
    row = rows[0]
    assert row["year"] == 2022
    assert row["aggregation"] == "CALENDAR_YEAR"
    assert row["wx_observed_days"] == 3
    assert row["wx_coverage_pct"] < 1
    assert row["wx_precip_sum_mm"] == 3.5
    assert row["wx_hot_days_ge_35c"] == 1
    assert row["wx_frost_days_lt_0c"] == 2

