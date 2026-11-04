import os
import uuid
from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///./tests/osh_agri_sqlite_test.sqlite3")
os.environ.setdefault("ENABLE_POSTGIS", "false")
os.environ.setdefault("JWT_SECRET", "sqlite-worker-test-secret-not-for-production")

from backend.app.main import app
from backend.app.db import SessionLocal
from backend.app.models import LocationClimateJob, LocationWeatherSnapshot, EnvironmentFeature, AnalysisJob
from backend.app import worker


def create_user_and_location(client: TestClient):
    email = f"worker-{uuid.uuid4().hex}@example.test"
    registered = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "worker-test-password-123"},
    )
    assert registered.status_code == 200, registered.text
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}

    saved = client.post(
        "/api/v1/locations",
        headers=headers,
        json={
            "country_iso3": "UZB",
            "name": "Worker test region",
            "admin_level": "ADM1",
            "climate_start_year": 2022,
            "geojson": {
                "type": "Polygon",
                "coordinates": [[
                    [69.1, 41.2], [69.3, 41.2], [69.3, 41.4],
                    [69.1, 41.4], [69.1, 41.2],
                ]],
            },
        },
    )
    assert saved.status_code == 200, saved.text
    return headers, saved.json()


def climate_frame():
    return pd.DataFrame({
        "date": pd.to_datetime(["2022-01-01", "2022-06-01", "2022-12-31"]),
        "T2M": [2.0, 28.0, 1.0],
        "T2M_MAX": [7.0, 36.0, 5.0],
        "T2M_MIN": [-3.0, 18.0, -5.0],
        "PRECTOTCORR": [1.0, 2.0, 0.5],
        "RH2M": [70.0, 35.0, 75.0],
        "WS2M": [2.0, 4.0, 1.0],
        "ALLSKY_SFC_SW_DWN": [5.0, 22.0, 4.0],
    })


def test_location_only_worker_persists_annual_climate_and_forecast(monkeypatch):
    async def fake_daily(*_args, **_kwargs):
        return climate_frame()

    async def fake_forecast(*_args, **_kwargs):
        return {
            "status": "AVAILABLE",
            "source": "Open-Meteo Forecast API",
            "current": {"temperature_2m": 22.0},
            "current_units": {"temperature_2m": "°C"},
            "daily": [{"date": "2026-11-04", "temperature_max_c": 24.0}],
            "forecast_days_returned": 1,
        }

    monkeypatch.setattr(worker, "fetch_daily_weather", fake_daily)
    monkeypatch.setattr(worker, "fetch_weather_forecast", fake_forecast)

    with TestClient(app) as client:
        headers, location = create_user_and_location(client)
        job_id = location["climate_job_id"]

        with SessionLocal() as db:
            job = db.get(LocationClimateJob, job_id)
            job.start_year = 2022
            job.end_year = 2022
            job.status = "RUNNING"
            worker.process_location_climate(db, job)

        report = client.get(
            f"/api/v1/locations/{location['id']}/climate",
            headers=headers,
        )
        assert report.status_code == 200, report.text
        body = report.json()
        assert len(body["annual"]) == 1
        assert body["annual"][0]["year"] == 2022
        assert body["annual"][0]["wx_observed_days"] == 3
        assert body["weather"]["status"] == "AVAILABLE"
        assert body["weather"]["current"]["temperature_2m"] == 22.0

        status = client.get(f"/api/v1/location-climate-jobs/{job_id}", headers=headers)
        assert status.json()["status"] == "COMPLETED"
        assert status.json()["result"]["yield_dataset_present"] is False
        assert status.json()["result"]["model_status"] == "NOT_RUN_NO_YIELD_DATA"


def test_dataset_worker_auto_runs_model_when_eight_yield_years_exist(monkeypatch):
    async def fake_daily(_lat, _lon, start, end):
        rows = []
        for year in range(2014, 2022):
            start_date = date(year - 1, 10, 1)
            mid_date = date(year, 3, 1)
            if start <= start_date <= end:
                rows.append((start_date, year))
            if start <= mid_date <= end:
                rows.append((mid_date, year))
        frame = pd.DataFrame({
            "date": pd.to_datetime([x[0] for x in rows]),
            "T2M": [8.0 + (x[1] - 2014) * 0.2 for x in rows],
            "T2M_MAX": [14.0 + (x[1] - 2014) * 0.2 for x in rows],
            "T2M_MIN": [1.0 + (x[1] - 2014) * 0.2 for x in rows],
            "PRECTOTCORR": [1.0 + (x[1] - 2014) * 0.1 for x in rows],
            "RH2M": [55.0 for _ in rows],
            "WS2M": [2.0 for _ in rows],
            "ALLSKY_SFC_SW_DWN": [12.0 for _ in rows],
        })
        return frame

    monkeypatch.setattr(worker, "fetch_daily_weather", fake_daily)

    with TestClient(app) as client:
        headers, location = create_user_and_location(client)
        csv_rows = ["year,yield_t_ha"]
        csv_rows += [f"{year},{3.0 + (year - 2014) * 0.05}" for year in range(2014, 2022)]
        upload = client.post(
            "/api/v1/datasets/upload",
            headers=headers,
            data={
                "location_id": str(location["id"]),
                "crop_code": "WHEAT",
                "season_start": "10-01",
                "season_end": "06-30",
            },
            files={"file": ("wheat.csv", "\n".join(csv_rows), "text/csv")},
        )
        assert upload.status_code == 200, upload.text
        job_id = upload.json()["analysis_job_id"]

        with SessionLocal() as db:
            job = db.get(AnalysisJob, job_id)
            job.status = "RUNNING"
            worker.process_one(db, job)

        job_status = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
        assert job_status.status_code == 200
        result = job_status.json()["result"]["automatic_analysis"]
        assert result["status"] == "COMPLETED"
        assert result["prediction"]["prediction_type"] == "CLIMATOLOGY_SCENARIO"
        assert result["prediction"]["oof_rows"] >= 1
