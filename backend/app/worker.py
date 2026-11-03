from __future__ import annotations
import time
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from .config import settings
from .db import SessionLocal
from .models import AnalysisJob, Dataset, Location, YieldObservation, EnvironmentFeature
from .services.nasa_power import fetch_daily_weather, aggregate_weather, crop_year_windows


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
    ds.status = "ENVIRONMENT_ENRICHED"
    job.progress = 100; job.status = "COMPLETED"; job.message = "NASA POWER ob-havo featurelari tayyor"
    job.result = {"weather_rows": len(rows), "period": [str(start), str(end)], "representative_point": {"lat": loc.centroid_lat, "lon": loc.centroid_lon},
                  "note": "NASA POWER polygon markaziga yaqin vakillik nuqtasi bo‘yicha olingan; butun poligonning zonal o‘rtachasi emas."}
    job.finished_at = datetime.now(timezone.utc)
    db.commit()


def main():
    print("OSH Global worker started", flush=True)
    while True:
        with SessionLocal() as db:
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
