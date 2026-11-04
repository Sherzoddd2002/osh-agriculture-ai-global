from __future__ import annotations
import time
from datetime import date, datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import settings
from .db import SessionLocal
from .models import AnalysisJob, Dataset, Location, YieldObservation, EnvironmentFeature, LocationClimateJob, LocationWeatherSnapshot
from .services.nasa_power import fetch_daily_weather, aggregate_weather, aggregate_calendar_year_weather, crop_year_windows
from .services.open_meteo import fetch_weather_forecast
from .ml.forecast import evaluate_and_predict


def process_one(db: Session, job: AnalysisJob):
    ds = db.get(Dataset, job.dataset_id)
    loc = db.get(Location, ds.location_id) if ds else None
    if not ds or not loc:
        raise RuntimeError("Dataset yoki location topilmadi")
    observations = db.scalars(select(YieldObservation).where(YieldObservation.dataset_id == ds.id).order_by(YieldObservation.year)).all()
    first, last = ds.first_year, ds.last_year
    windows = list(crop_year_windows(first, last, ds.season_start, ds.season_end))
    start, end = min(w[1] for w in windows), max(w[2] for w in windows)
    job.progress = 10; job.message = "NASA POWER ob-havo qatori olinmoqda"; db.commit()
    import asyncio
    daily = asyncio.run(fetch_daily_weather(loc.centroid_lat, loc.centroid_lon, start, end))
    rows = aggregate_weather(daily, first, last, ds.season_start, ds.season_end)
    job.progress = 75; job.message = "Ob-havo qatori hosil yillari bilan birlashtirilmoqda"; db.commit()
    for row in rows:
        year = int(row.pop("year"))
        existing = db.scalar(select(EnvironmentFeature).where(EnvironmentFeature.location_id == loc.id, EnvironmentFeature.crop_code == ds.crop_code, EnvironmentFeature.year == year))
        if existing:
            existing.features = row
            existing.source_status = {"NASA_POWER": "AVAILABLE" if row.get("wx_observed_days", 0) else "NO_DATA",
                                      "SENTINEL2_NDVI": "NOT_CONFIGURED", "NASA_SMAP": "NOT_CONFIGURED", "SOILGRIDS": "NOT_CONFIGURED"}
        else:
            db.add(EnvironmentFeature(location_id=loc.id, crop_code=ds.crop_code, year=year, features=row,
                source_status={"NASA_POWER": "AVAILABLE" if row.get("wx_observed_days", 0) else "NO_DATA",
                               "SENTINEL2_NDVI": "NOT_CONFIGURED", "NASA_SMAP": "NOT_CONFIGURED", "SOILGRIDS": "NOT_CONFIGURED"}))
    db.flush()

    # Automatically evaluate a local model when enough observed yield years exist.
    weather_by_year = {int(row["year"]): row for row in rows}
    aligned = []
    for observation in observations:
        weather = weather_by_year.get(int(observation.year))
        if weather:
            aligned.append({"year": int(observation.year), "yield_t_ha": float(observation.yield_t_ha), **weather})

    automatic_analysis = {
        "status": "NOT_RUN",
        "reason": "Model uchun kamida 8 ta hosildorlik kuzatuvi va kamida 2 ta ob-havo feature kerak.",
        "observed_yield_rows": len(observations),
        "weather_aligned_rows": len(aligned),
    }
    if len(observations) >= 8 and len(aligned) >= 8:
        try:
            prediction = evaluate_and_predict(aligned, target_year=int(ds.last_year) + 1)
            automatic_analysis = {
                "status": "COMPLETED",
                "mode": "USER_DATASET_RESEARCH_SCENARIO",
                "prediction": prediction,
                "note": "Natija foydalanuvchining shu datasetiga moslangan; shared global model emas."
            }
        except ValueError as exc:
            automatic_analysis = {"status": "NOT_RUN", "reason": str(exc)}

    ds.status = "ANALYZED" if automatic_analysis["status"] == "COMPLETED" else "ENVIRONMENT_ENRICHED"
    job.progress = 100; job.status = "COMPLETED"; job.message = (
        "Ob-havo va avtomatik model tahlili tayyor"
        if automatic_analysis["status"] == "COMPLETED"
        else "Ob-havo ma’lumotlari tayyor; model uchun yetarli mos hosildorlik qatori yo‘q"
    )
    job.result = {
        "weather_rows": len(rows),
        "period": [str(start), str(end)],
        "representative_point": {"lat": loc.centroid_lat, "lon": loc.centroid_lon},
        "automatic_analysis": automatic_analysis,
        "note": "NASA POWER polygon ichidagi vakillik nuqtasidan olinadi; butun poligonning zonal o‘rtachasi emas."
    }
    job.finished_at = datetime.now(timezone.utc)
    db.commit()


def process_location_climate(db: Session, job: LocationClimateJob):
    loc = db.get(Location, job.location_id)
    if not loc:
        raise RuntimeError("Hudud topilmadi yoki o‘chirilgan")

    job.progress = 10
    job.message = "NASA POWER tarixiy kunlik ob-havo qatori olinmoqda"
    db.commit()

    start = date(max(1981, job.start_year), 1, 1)
    end = min(date(job.end_year, 12, 31), date.today())
    daily = __import__("asyncio").run(fetch_daily_weather(loc.centroid_lat, loc.centroid_lon, start, end))
    annual = aggregate_calendar_year_weather(daily, job.start_year, job.end_year)

    job.progress = 70
    job.message = "Yillik iqlim ko‘rsatkichlari SQL bazasiga yozilmoqda"
    db.commit()

    for row in annual:
        year = int(row["year"])
        existing = db.scalar(select(EnvironmentFeature).where(
            EnvironmentFeature.location_id == loc.id,
            EnvironmentFeature.crop_code == "CLIMATE",
            EnvironmentFeature.year == year,
        ))
        values = {k: v for k, v in row.items() if k != "year"}
        source_status = {
            "NASA_POWER": "AVAILABLE" if row.get("wx_observed_days", 0) else "NO_DATA",
            "data_type": "HISTORICAL_ANNUAL_POINT_WEATHER",
        }
        if existing:
            existing.features = values
            existing.source_status = source_status
        else:
            db.add(EnvironmentFeature(
                location_id=loc.id, crop_code="CLIMATE", year=year,
                features=values, source_status=source_status
            ))

    job.progress = 82
    job.message = "Joriy ob-havo va qisqa muddatli prognoz olinmoqda"
    db.commit()
    forecast = __import__("asyncio").run(fetch_weather_forecast(loc.centroid_lat, loc.centroid_lon, 16))
    snapshot = db.scalar(select(LocationWeatherSnapshot).where(LocationWeatherSnapshot.location_id == loc.id))
    if snapshot:
        snapshot.payload = forecast
        snapshot.fetched_at = datetime.now(timezone.utc)
    else:
        db.add(LocationWeatherSnapshot(
            location_id=loc.id, payload=forecast, fetched_at=datetime.now(timezone.utc)
        ))

    job.progress = 100
    job.status = "COMPLETED"
    job.message = "Hududning yillik iqlim tarixi va joriy ob-havo prognozi tayyor"
    job.result = {
        "annual_rows": len(annual),
        "historical_period": [str(start), str(end)],
        "forecast_days": forecast.get("forecast_days_returned", 0),
        "yield_dataset_present": False,
        "model_status": "NOT_RUN_NO_YIELD_DATA",
        "representative_point": {"lat": loc.centroid_lat, "lon": loc.centroid_lon},
        "note": "Bu vakillik nuqtasi bo‘yicha iqlim tahlili; poligonning zonal o‘rtachasi emas."
    }
    job.finished_at = datetime.now(timezone.utc)
    db.commit()


def main():
    print("OSH Global worker started", flush=True)
    while True:
        with SessionLocal() as db:
            climate_job = db.scalar(
                select(LocationClimateJob)
                .where(LocationClimateJob.status == "QUEUED")
                .order_by(LocationClimateJob.created_at)
                .with_for_update(skip_locked=True).limit(1)
            )
            if climate_job:
                climate_job.status = "RUNNING"
                climate_job.started_at = datetime.now(timezone.utc)
                climate_job.progress = 1
                db.commit()
                try:
                    process_location_climate(db, climate_job)
                except Exception as exc:
                    db.rollback()
                    failed = db.get(LocationClimateJob, climate_job.id)
                    if failed:
                        failed.status = "FAILED"
                        failed.error = str(exc)
                        failed.message = "Hudud iqlim tahlili bajarilmadi"
                        failed.finished_at = datetime.now(timezone.utc)
                        db.commit()
                    print(f"location climate job {climate_job.id} failed: {exc}", flush=True)
                time.sleep(settings.worker_poll_seconds)
                continue

            job = db.scalar(select(AnalysisJob).where(AnalysisJob.status == "QUEUED").order_by(AnalysisJob.created_at).with_for_update(skip_locked=True).limit(1))
            if job:
                job.status = "RUNNING"; job.started_at = datetime.now(timezone.utc); job.progress = 1; db.commit()
                try:
                    process_one(db, job)
                except Exception as exc:
                    db.rollback()
                    failed = db.get(AnalysisJob, job.id)
                    if failed:
                        failed.status = "FAILED"; failed.error = str(exc); failed.message = "Ma’lumot yig‘ish bajarilmadi"; failed.finished_at = datetime.now(timezone.utc)
                        ds = db.get(Dataset, failed.dataset_id)
                        if ds: ds.status = "PROCESSING_FAILED"
                        db.commit()
                    print(f"job {job.id} failed: {exc}", flush=True)
        time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    main()
