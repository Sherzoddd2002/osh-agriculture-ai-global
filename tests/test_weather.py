from datetime import date
import pandas as pd
from backend.app.services.nasa_power import aggregate_weather


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
