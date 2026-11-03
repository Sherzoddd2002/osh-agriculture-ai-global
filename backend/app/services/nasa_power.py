from datetime import date
import httpx
import numpy as np
import pandas as pd
from ..config import settings

PARAMETERS = ["T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR", "RH2M", "WS2M", "ALLSKY_SFC_SW_DWN"]


async def fetch_daily_weather(lat: float, lon: float, start: date, end: date) -> pd.DataFrame:
    if end < start:
        return pd.DataFrame()
    # NASA POWER daily service starts 1981-01-01; clip only the start bound.
    start = max(start, date(1981, 1, 1))
    today = date.today()
    end = min(end, today)
    if end < start:
        return pd.DataFrame()
    params = {
        "parameters": ",".join(PARAMETERS),
        "community": "AG",
        "longitude": f"{lon:.5f}",
        "latitude": f"{lat:.5f}",
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
        "time-standard": "UTC",
    }
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
        response = await client.get(settings.nasa_power_base_url, params=params, headers={"Accept": "application/json"})
        response.raise_for_status()
        payload = response.json()
    raw = payload.get("properties", {}).get("parameter", {})
    if not raw:
        raise ValueError("NASA POWER javobida parameter ma’lumotlari topilmadi")
    frames = []
    for parameter, values in raw.items():
        s = pd.Series(values, name=parameter, dtype="float64")
        s.index = pd.to_datetime(s.index, format="%Y%m%d", errors="coerce")
        s = s.replace(-999, np.nan)
        frames.append(s)
    df = pd.concat(frames, axis=1).sort_index()
    df.index.name = "date"
    return df.reset_index()


def crop_year_windows(first_year: int, last_year: int, season_start: str, season_end: str):
    sm, sd = (int(x) for x in season_start.split("-"))
    em, ed = (int(x) for x in season_end.split("-"))
    for year in range(first_year, last_year + 1):
        start_year = year - 1 if (sm, sd) > (em, ed) else year
        yield year, date(start_year, sm, sd), date(year, em, ed)


def aggregate_weather(df: pd.DataFrame, first_year: int, last_year: int, season_start: str, season_end: str) -> list[dict]:
    results = []
    if df.empty:
        return results
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])
    for year, start, end in crop_year_windows(first_year, last_year, season_start, season_end):
        part = d[(d.date >= pd.Timestamp(start)) & (d.date <= pd.Timestamp(end))].copy()
        if part.empty:
            continue
        n_expected = (end - start).days + 1
        row = {"year": year, "wx_expected_days": n_expected, "wx_observed_days": int(part["T2M"].notna().sum())}
        row["wx_coverage_pct"] = round(100 * row["wx_observed_days"] / n_expected, 2)
        for col, key in [("T2M", "wx_t2m_mean_c"), ("T2M_MAX", "wx_tmax_mean_c"), ("T2M_MIN", "wx_tmin_mean_c"), ("RH2M", "wx_rh_mean_pct"), ("WS2M", "wx_wind_mean_m_s"), ("ALLSKY_SFC_SW_DWN", "wx_solar_mean_mj_m2_day")]:
            row[key] = float(part[col].mean()) if col in part and part[col].notna().any() else None
        row["wx_precip_sum_mm"] = float(part["PRECTOTCORR"].sum(min_count=1)) if "PRECTOTCORR" in part else None
        row["wx_hot_days_ge_35c"] = int((part["T2M_MAX"] >= 35).sum()) if "T2M_MAX" in part else None
        row["wx_frost_days_lt_0c"] = int((part["T2M_MIN"] < 0).sum()) if "T2M_MIN" in part else None
        if "T2M" in part:
            row["wx_gdd_base5_cday"] = float((part["T2M"] - 5).clip(lower=0).sum(min_count=1))
        else:
            row["wx_gdd_base5_cday"] = None
        # Do not turn missing values into zero. Coverage is carried with every row.
        results.append(row)
    return results
