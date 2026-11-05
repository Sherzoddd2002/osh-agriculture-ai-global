from __future__ import annotations
import hashlib
import io
import json
import re
from datetime import date, datetime, timezone
from typing import Optional
import pandas as pd
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from shapely.geometry import shape, mapping
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from .config import settings
from .db import SessionLocal, init_db
from .models import User, Location, Dataset, YieldObservation, EnvironmentFeature, AnalysisJob, LocationClimateJob, LocationWeatherSnapshot, GlobalRasterSummary
from .security import hash_password, verify_password, create_access_token, current_user, get_db
from .services.boundaries import get_boundary_geojson
from .services.nasa_power import fetch_daily_weather, aggregate_calendar_year_weather
from .services.open_meteo import fetch_weather_forecast
from .services.connectors import SOURCE_REGISTRY
from .services.faostat_catalog import classify_faostat_item, item_type_label, CROP, AGGREGATE, PRODUCT_FORM
from .ml.forecast import evaluate_and_predict

app = FastAPI(title=settings.app_name, version="0.1.0", description="Global agricultural data integration and yield forecasting foundation")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.on_event("startup")
def startup():
    if settings.app_env.lower() == "production":
        if settings.jwt_secret == "DEV_ONLY_CHANGE_ME" or len(settings.jwt_secret) < 32:
            raise RuntimeError("Production rejimida JWT_SECRET kamida 32 belgili maxfiy qiymat bo‘lishi kerak")
        if not settings.database_url.startswith(("postgresql+psycopg://", "postgresql://")):
            raise RuntimeError("Production server SQLite bilan ishga tushmaydi. Markaziy PostgreSQL DATABASE_URL talab qilinadi.")
    init_db()


@app.get("/", include_in_schema=False)
def home():
    return FileResponse("frontend/index.html")


@app.get("/assets/{filename}", include_in_schema=False)
def asset(filename: str):
    if filename not in {"hero-field.jpg"}:
        raise HTTPException(404, "Asset not found")
    return FileResponse(f"frontend/assets/{filename}")


@app.get("/app.js", include_in_schema=False)
def js():
    return FileResponse("frontend/app.js", media_type="application/javascript")


@app.get("/styles.css", include_in_schema=False)
def css():
    return FileResponse("frontend/styles.css", media_type="text/css")


@app.get("/api/v1/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"ok": True, "service": "OSH Agriculture AI Global", "version": "0.1.0", "database": "connected"}


@app.get("/api/v1/sources")
def sources():
    return {"sources": SOURCE_REGISTRY}


@app.get("/api/v1/boundaries/{iso3}/{admin_level}")
async def boundaries(iso3: str, admin_level: str):
    return await get_boundary_geojson(iso3, admin_level)


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=10, max_length=200)


class LoginRequest(BaseModel):
    email: str
    password: str


@app.post("/api/v1/auth/register")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(400, "Email formati noto‘g‘ri")
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, "Bu email allaqachon ro‘yxatdan o‘tgan")
    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user); db.commit(); db.refresh(user)
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": {"id": user.id, "email": user.email}}


@app.post("/api/v1/auth/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Email yoki parol noto‘g‘ri")
    return {"access_token": create_access_token(user.id), "token_type": "bearer", "user": {"id": user.id, "email": user.email}}


class LocationCreate(BaseModel):
    country_iso3: str = Field(min_length=3, max_length=3)
    name: str = Field(min_length=1, max_length=250)
    admin_level: str = "ADM1"
    geojson: dict
    source: str = "geoBoundaries"
    climate_start_year: int = Field(default=2010, ge=1981, le=2200)


@app.post("/api/v1/locations")
def create_location(payload: LocationCreate, user: User = Depends(current_user), db: Session = Depends(get_db)):
    try:
        geom = shape(payload.geojson.get("geometry", payload.geojson))
        if geom.is_empty or not geom.is_valid:
            raise ValueError("Geometry bo‘sh yoki yaroqsiz")
        if geom.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError("Faqat Polygon yoki MultiPolygon qabul qilinadi")
        centroid = geom.representative_point()
    except Exception as exc:
        raise HTTPException(400, f"GeoJSON tekshiruvdan o‘tmadi: {exc}")
    loc = Location(owner_id=user.id, country_iso3=payload.country_iso3.upper(), name=payload.name,
                   admin_level=payload.admin_level.upper(), centroid_lat=float(centroid.y), centroid_lon=float(centroid.x),
                   geojson=payload.geojson, source=payload.source)
    db.add(loc); db.flush()

    if settings.enable_postgis:
        geom_json = json.dumps(mapping(geom), separators=(",", ":"))
        db.execute(text("UPDATE locations SET geom = ST_SetSRID(ST_GeomFromGeoJSON(:geojson), 4326) WHERE id = :id"),
                   {"geojson": geom_json, "id": loc.id})

    db.commit(); db.refresh(loc)

    climate_job = LocationClimateJob(
        owner_id=user.id,
        location_id=loc.id,
        start_year=payload.climate_start_year,
        end_year=date.today().year,
        status="QUEUED",
        progress=0,
        message="Hudud uchun yillik iqlim ma’lumotlari navbatga qo‘yildi",
    )
    db.add(climate_job)
    db.commit()
    db.refresh(climate_job)

    return {"id": loc.id, "name": loc.name, "country_iso3": loc.country_iso3, "admin_level": loc.admin_level,
            "centroid": {"lat": loc.centroid_lat, "lon": loc.centroid_lon},
            "climate_job_id": climate_job.id, "climate_status": climate_job.status}


@app.get("/api/v1/datasets")
def list_datasets(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Dataset).where(Dataset.owner_id == user.id).order_by(Dataset.created_at.desc())).all()
    return [{"id": x.id, "name": x.name, "location_id": x.location_id, "crop_code": x.crop_code,
             "row_count": x.row_count, "first_year": x.first_year, "last_year": x.last_year,
             "status": x.status, "global_consent": x.global_consent} for x in rows]


@app.get("/api/v1/locations")
def list_locations(user: User = Depends(current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Location).where(Location.owner_id == user.id).order_by(Location.created_at.desc())).all()
    return [{"id": x.id, "country_iso3": x.country_iso3, "name": x.name, "admin_level": x.admin_level} for x in rows]


@app.post("/api/v1/locations/{location_id}/analyze")
def analyze_location(location_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    loc = db.scalar(select(Location).where(Location.id == location_id, Location.owner_id == user.id))
    if not loc:
        raise HTTPException(404, "Hudud topilmadi")
    existing = db.scalar(
        select(LocationClimateJob)
        .where(LocationClimateJob.location_id == loc.id, LocationClimateJob.owner_id == user.id,
               LocationClimateJob.status.in_(["QUEUED", "RUNNING"]))
        .order_by(LocationClimateJob.created_at.desc())
    )
    if existing:
        return {"job_id": existing.id, "status": existing.status, "message": existing.message}
    job = LocationClimateJob(
        owner_id=user.id, location_id=loc.id, start_year=2010, end_year=date.today().year,
        status="QUEUED", progress=0, message="Hudud iqlimi qayta tahlilga qo‘yildi"
    )
    db.add(job); db.commit(); db.refresh(job)
    return {"job_id": job.id, "status": job.status, "message": job.message}


@app.get("/api/v1/location-climate-jobs/{job_id}")
def location_climate_job_status(job_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = db.scalar(select(LocationClimateJob).where(
        LocationClimateJob.id == job_id, LocationClimateJob.owner_id == user.id
    ))
    if not job:
        raise HTTPException(404, "Iqlim job topilmadi")
    return {"id": job.id, "status": job.status, "progress": job.progress,
            "message": job.message, "result": job.result, "error": job.error}


@app.get("/api/v1/locations/{location_id}/climate")
def location_climate(location_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    loc = db.scalar(select(Location).where(Location.id == location_id, Location.owner_id == user.id))
    if not loc:
        raise HTTPException(404, "Hudud topilmadi")
    rows = db.scalars(
        select(EnvironmentFeature)
        .where(EnvironmentFeature.location_id == loc.id, EnvironmentFeature.crop_code == "CLIMATE")
        .order_by(EnvironmentFeature.year)
    ).all()
    snapshot = db.scalar(select(LocationWeatherSnapshot).where(LocationWeatherSnapshot.location_id == loc.id))
    latest_job = db.scalar(
        select(LocationClimateJob)
        .where(LocationClimateJob.location_id == loc.id, LocationClimateJob.owner_id == user.id)
        .order_by(LocationClimateJob.created_at.desc())
    )
    return {
        "location": {"id": loc.id, "name": loc.name, "country_iso3": loc.country_iso3,
                     "centroid": {"lat": loc.centroid_lat, "lon": loc.centroid_lon}},
        "annual": [{"year": x.year, **x.features, "source_status": x.source_status} for x in rows],
        "weather": snapshot.payload if snapshot else None,
        "weather_fetched_at": snapshot.fetched_at.isoformat() if snapshot else None,
        "latest_job": ({"id": latest_job.id, "status": latest_job.status,
                        "progress": latest_job.progress, "message": latest_job.message,
                        "result": latest_job.result, "error": latest_job.error}
                       if latest_job else None),
        "sources": SOURCE_REGISTRY,
    }


@app.post("/api/v1/datasets/upload")
async def upload_dataset(
    location_id: int = Form(...), crop_code: str = Form(...), name: str = Form("My crop dataset"),
    year_column: str = Form("year"), yield_column: str = Form("yield_t_ha"),
    area_column: Optional[str] = Form(None), production_column: Optional[str] = Form(None),
    area_basis: str = Form("unknown"), season_start: str = Form("10-01"), season_end: str = Form("06-30"),
    global_consent: bool = Form(False), file: UploadFile = File(...),
    user: User = Depends(current_user), db: Session = Depends(get_db),
):
    loc = db.scalar(select(Location).where(Location.id == location_id, Location.owner_id == user.id))
    if not loc:
        raise HTTPException(404, "Tanlangan hudud topilmadi yoki sizga tegishli emas")
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "MVP hozircha CSV formatini qabul qiladi")
    raw = await file.read()
    if len(raw) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Fayl {settings.max_upload_mb} MB limitdan katta")
    try:
        df = pd.read_csv(io.BytesIO(raw))
    except Exception as exc:
        raise HTTPException(400, f"CSV o‘qilmadi: {exc}")
    if year_column not in df or yield_column not in df:
        raise HTTPException(400, f"Kerakli ustunlar topilmadi. CSV ustunlari: {list(df.columns)}")
    if len(df) == 0 or len(df) > 10000:
        raise HTTPException(400, "CSV 1–10 000 qator oralig‘ida bo‘lishi kerak")
    years = pd.to_numeric(df[year_column], errors="coerce")
    yields = pd.to_numeric(df[yield_column], errors="coerce")
    invalid = years.isna() | yields.isna() | (yields < 0) | (yields > 30)
    if invalid.any():
        raise HTTPException(400, f"{int(invalid.sum())} qator year/yield tekshiruvidan o‘tmadi. Yield manfiy bo‘lmasligi va t/ha birligida berilishi kerak.")
    normalized_years = years.astype(int)
    if normalized_years.duplicated().any():
        raise HTTPException(400, "Har bir datasetda bitta yil uchun bitta hosildorlik qatori bo‘lishi kerak; takroriy yillar topildi")
    if normalized_years.min() < 1900 or normalized_years.max() > datetime.now(timezone.utc).year + 1:
        raise HTTPException(400, "Yil qiymatlari 1900-yildan hozirgacha bo‘lishi kerak")
    if not re.fullmatch(r"\d{2}-\d{2}", season_start) or not re.fullmatch(r"\d{2}-\d{2}", season_end):
        raise HTTPException(400, "Mavsum sanalari MM-DD formatida bo‘lishi kerak")
    from datetime import date
    try:
        date(2000, int(season_start[:2]), int(season_start[3:]))
        date(2000, int(season_end[:2]), int(season_end[3:]))
    except ValueError:
        raise HTTPException(400, "Mavsum sanasi haqiqiy kalendar sana bo‘lishi kerak")
    if season_start == "02-29" or season_end == "02-29":
        raise HTTPException(400, "Mavsum chegarasi sifatida 29-fevral ishlatilmaydi")
    area = pd.to_numeric(df[area_column], errors="coerce") if area_column and area_column in df else pd.Series([None] * len(df))
    production = pd.to_numeric(df[production_column], errors="coerce") if production_column and production_column in df else pd.Series([None] * len(df))
    sha = hashlib.sha256(raw).hexdigest()
    dataset = Dataset(owner_id=user.id, location_id=loc.id, name=name[:250], crop_code=crop_code.upper(), area_basis=area_basis,
                      season_start=season_start, season_end=season_end, global_consent=global_consent,
                      source_sha256=sha, row_count=len(df), first_year=int(normalized_years.min()), last_year=int(normalized_years.max()), status="UPLOADED")
    db.add(dataset); db.flush()
    for i in range(len(df)):
        db.add(YieldObservation(dataset_id=dataset.id, year=int(normalized_years.iloc[i]), yield_t_ha=float(yields.iloc[i]),
                                area_ha=float(area.iloc[i]) if pd.notna(area.iloc[i]) else None,
                                production_t=float(production.iloc[i]) if pd.notna(production.iloc[i]) else None,
                                target_status="OBSERVED"))
    db.commit(); db.refresh(dataset)

    analysis_job = AnalysisJob(
        owner_id=user.id, dataset_id=dataset.id, job_type="ENVIRONMENT_AND_AUTO_MODEL",
        status="QUEUED", progress=0, message="Iqlim ma’lumotlari va avtomatik model tahlili navbatga qo‘yildi"
    )
    dataset.status = "PROCESSING"
    db.add(analysis_job)
    db.commit()
    db.refresh(analysis_job)

    return {"dataset_id": dataset.id, "name": dataset.name, "row_count": dataset.row_count,
            "year_range": [dataset.first_year, dataset.last_year], "global_training_consent": dataset.global_consent,
            "status": dataset.status, "sha256": sha, "analysis_job_id": analysis_job.id}


@app.post("/api/v1/datasets/{dataset_id}/process")
def process_dataset(dataset_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ds = db.scalar(select(Dataset).where(Dataset.id == dataset_id, Dataset.owner_id == user.id))
    if not ds:
        raise HTTPException(404, "Dataset topilmadi")
    job = AnalysisJob(owner_id=user.id, dataset_id=ds.id, status="QUEUED", progress=0, message="Ob-havo ma’lumotlari navbatga qo‘yildi")
    ds.status = "PROCESSING"
    db.add(job); db.commit(); db.refresh(job)
    return {"job_id": job.id, "status": job.status, "message": job.message}


@app.get("/api/v1/jobs/{job_id}")
def job_status(job_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    job = db.scalar(select(AnalysisJob).where(AnalysisJob.id == job_id, AnalysisJob.owner_id == user.id))
    if not job:
        raise HTTPException(404, "Job topilmadi")
    return {"id": job.id, "status": job.status, "progress": job.progress, "message": job.message, "result": job.result, "error": job.error}


@app.get("/api/v1/datasets/{dataset_id}/coverage")
def dataset_coverage(dataset_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ds = db.scalar(select(Dataset).where(Dataset.id == dataset_id, Dataset.owner_id == user.id))
    if not ds:
        raise HTTPException(404, "Dataset topilmadi")
    obs = db.scalars(select(YieldObservation).where(YieldObservation.dataset_id == ds.id).order_by(YieldObservation.year)).all()
    env = db.scalars(select(EnvironmentFeature).where(EnvironmentFeature.location_id == ds.location_id, EnvironmentFeature.crop_code == ds.crop_code).order_by(EnvironmentFeature.year)).all()
    env_map = {x.year: x for x in env}
    years = []
    for o in obs:
        features = env_map.get(o.year)
        years.append({"year": o.year, "yield_t_ha": o.yield_t_ha, "target_status": o.target_status,
                      "weather_status": (features.source_status.get("NASA_POWER", "MISSING") if features else "MISSING"),
                      "weather_coverage_pct": (features.features.get("wx_coverage_pct") if features else None)})
    return {"dataset_id": ds.id, "observed_rows": len(obs), "environment_years": len(env), "years": years,
            "sources": SOURCE_REGISTRY}


class PredictionRequest(BaseModel):
    dataset_id: int
    target_year: int = Field(ge=1900, le=2200)
    model: Optional[str] = None



class GlobalYieldRequest(BaseModel):
    country_iso3: str = Field(min_length=3,max_length=3)
    crop_code: str = Field(min_length=2,max_length=64)
    target_year: int = Field(ge=1900,le=2200)

class GlobalRasterSummaryRequest(BaseModel):
    geojson: dict
    crop_code: str = Field(min_length=4, max_length=4, pattern="^[a-zA-Z]{4}$")
    technology: str = Field(default="all", pattern="^(all|irrigated|rainfed)$")
    location_name: Optional[str] = Field(default=None, max_length=250)
    admin_level: Optional[str] = Field(default=None, pattern="^ADM[0-5]$")


@app.get("/api/v1/global-raster-catalog")
def global_raster_catalog():
    from .services.global_raster_catalog import catalog_summary
    return catalog_summary()


@app.get("/api/v1/global-raster-status")
def global_raster_status():
    from .services.global_raster_catalog import (
        CROPGRIDS,
        MAPSPAM,
        default_global_data_dir,
        mapspam_cog_assets,
    )

    root = default_global_data_dir()
    mapspam_dir = root / MAPSPAM["dataset_id"]
    assets = []
    for asset in mapspam_cog_assets():
        path = mapspam_dir / asset["filename"]
        assets.append({
            "asset_id": asset["asset_id"],
            "filename": asset["filename"],
            "required_for_summary": (
                asset["asset_id"] in {
                    "physical_area-all", "harvested_area-all",
                    "production-all", "yield-all",
                }
            ),
            "downloaded": path.is_file() and path.stat().st_size > 0,
            "bytes": path.stat().st_size if path.is_file() else 0,
        })
    cropgrids_path = (
        root / CROPGRIDS["dataset_id"] / CROPGRIDS["filename"]
    )
    return {
        "storage": "server-local",
        "data_directory_configured": True,
        "mapspam": {
            "dataset_id": MAPSPAM["dataset_id"],
            "reference_year": MAPSPAM["reference_year"],
            "assets": assets,
            "core_ready": all(
                item["downloaded"]
                for item in assets
                if item["required_for_summary"]
            ) and next(
                item["downloaded"] for item in assets
                if item["asset_id"] == "crop-codes"
            ),
        },
        "cropgrids": {
            "dataset_id": CROPGRIDS["dataset_id"],
            "reference_year": CROPGRIDS["reference_year"],
            "downloaded": cropgrids_path.is_file(),
            "bytes": cropgrids_path.stat().st_size if cropgrids_path.is_file() else 0,
            "expected_bytes": CROPGRIDS["expected_size_bytes"],
        },
    }


@app.post("/api/v1/global-raster-summary/mapspam")
def global_raster_mapspam_summary(
    payload: GlobalRasterSummaryRequest,
    user: User = Depends(current_user),
):
    from .services.global_raster_catalog import (
        MAPSPAM,
        MAPSPAM_CROPS,
        default_global_data_dir,
    )
    from .services.global_raster_zonal import aggregate_mapspam_zone

    crop_lookup = {code: name for code, name in MAPSPAM_CROPS}
    crop_code = payload.crop_code.strip().lower()
    if crop_code not in crop_lookup:
        raise HTTPException(
            422,
            f"MAPSPAM crop_code '{crop_code}' not found. "
            "Use one of the 46 codes from /api/v1/global-raster-catalog.",
        )

    geojson_geometry = payload.geojson.get("geometry", payload.geojson)
    try:
        geom = shape(geojson_geometry)
        if geom.is_empty or not geom.is_valid:
            raise ValueError("GeoJSON geometry is empty or invalid")
        if geom.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError("Only Polygon or MultiPolygon geometries are supported")
        result = aggregate_mapspam_zone(
            geometry=mapping(geom),
            crop_band=list(crop_lookup).index(crop_code) + 1,
            data_dir=default_global_data_dir(),
            technology=payload.technology,
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            503,
            f"MAPSPAM assets are not fully synced. "
            f"Run the global raster sync command. Details: {exc}",
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc

    result.update({
        "crop_code": crop_code,
        "crop_name": crop_lookup[crop_code],
        "source": "IFPRI MAPSPAM 2020 v2r2",
        "source_year": MAPSPAM["reference_year"],
        "source_license": MAPSPAM["license"],
        "spatial_level": payload.admin_level,
        "location_name": payload.location_name,
        "interpretation": (
            "2020 gridded spatial estimate. This is not a current-year observation "
            "or field-level measurement."
        ),
    })
    return result



@app.get("/api/v1/global-raster-summaries")
def list_global_raster_summaries(
    country_iso3: Optional[str] = None,
    admin_level: Optional[str] = None,
    admin_id: Optional[str] = None,
    crop_code: Optional[str] = None,
    source_year: Optional[int] = None,
    technology: Optional[str] = None,
    dataset_id: Optional[str] = None,
    limit: int = 1000,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Read persisted official raster summaries; NULL yields remain NULL."""
    if limit < 1 or limit > 5000:
        raise HTTPException(422, "limit 1–5000 oralig‘ida bo‘lishi kerak")
    if offset < 0:
        raise HTTPException(422, "offset manfiy bo‘lishi mumkin emas")

    conditions = []
    if country_iso3:
        country = country_iso3.strip().upper()
        if not re.fullmatch(r"[A-Z]{3}", country):
            raise HTTPException(422, "country_iso3 ISO-3 formatida bo‘lishi kerak")
        conditions.append(GlobalRasterSummary.country_iso3 == country)
    if admin_level:
        level = admin_level.strip().upper()
        if level not in {"ADM0", "ADM1"}:
            raise HTTPException(422, "admin_level ADM0 yoki ADM1 bo‘lishi kerak")
        conditions.append(GlobalRasterSummary.admin_level == level)
    if admin_id:
        conditions.append(GlobalRasterSummary.admin_id == admin_id.strip())
    if crop_code:
        crop = crop_code.strip().lower()
        from .services.global_raster_catalog import MAPSPAM_CROPS
        if crop not in {code for code, _ in MAPSPAM_CROPS}:
            raise HTTPException(422, "Noma’lum MAPSPAM crop_code")
        conditions.append(GlobalRasterSummary.crop_code == crop)
    if source_year is not None:
        if source_year < 1900 or source_year > 2200:
            raise HTTPException(422, "source_year noto‘g‘ri")
        conditions.append(GlobalRasterSummary.source_year == source_year)
    if technology:
        technology_value = technology.strip().lower()
        if technology_value not in {"all", "irrigated", "rainfed"}:
            raise HTTPException(422, "technology all, irrigated yoki rainfed bo‘lishi kerak")
        conditions.append(GlobalRasterSummary.technology == technology_value)
    if dataset_id:
        conditions.append(GlobalRasterSummary.dataset_id == dataset_id.strip())

    total = db.scalar(
        select(func.count()).select_from(GlobalRasterSummary).where(*conditions)
    ) or 0
    rows = db.scalars(
        select(GlobalRasterSummary)
        .where(*conditions)
        .order_by(
            GlobalRasterSummary.country_iso3,
            GlobalRasterSummary.admin_level,
            GlobalRasterSummary.admin_name,
            GlobalRasterSummary.crop_code,
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "source": "IFPRI MAPSPAM",
        "count": total,
        "returned": len(rows),
        "limit": limit,
        "offset": offset,
        "items": [
            {
                "dataset_id": row.dataset_id,
                "country_iso3": row.country_iso3,
                "country_name": row.country_name,
                "admin_level": row.admin_level,
                "admin_name": row.admin_name,
                "admin_id": row.admin_id,
                "boundary_source": row.boundary_source,
                "boundary_year": row.boundary_year,
                "source_year": row.source_year,
                "technology": row.technology,
                "crop_code": row.crop_code,
                "crop_name": row.crop_name,
                "crop_band": row.crop_band,
                "physical_area_ha": row.physical_area_ha,
                "harvested_area_ha": row.harvested_area_ha,
                "production_t": row.production_t,
                "yield_t_ha_area_weighted": row.yield_t_ha_area_weighted,
                "valid_cells": row.valid_cells,
                "yield_crosscheck_abs_kg_ha": row.yield_crosscheck_abs_kg_ha,
                "spatial_status": row.spatial_status,
                "computed_at_utc": row.computed_at_utc,
                "imported_at": row.imported_at,
                "interpretation": (
                    "2020 gridded spatial estimate, not a current-year observation "
                    "or field-level measurement."
                ),
            }
            for row in rows
        ],
    }


@app.get("/api/v1/global-crops")
def global_crops(item_type: str = "ALL", db: Session = Depends(get_db)):
    requested_type = item_type.strip().upper()
    if requested_type not in {"ALL", CROP, AGGREGATE, PRODUCT_FORM}:
        raise HTTPException(422, "item_type ALL, CROP, AGGREGATE yoki PRODUCT_FORM bo‘lishi kerak")
    rows = db.execute(text("""
        SELECT crop_code, item_code, MIN(crop_name) AS crop_name,
               COUNT(*) AS observations, MIN(year) AS first_year,
               MAX(year) AS last_year,
               COUNT(DISTINCT country_iso3) AS countries
        FROM global_crop_statistics
        WHERE source_code = 'FAOSTAT_QCL'
        GROUP BY crop_code, item_code
        ORDER BY crop_name, crop_code
    """)).mappings().all()
    items = []
    for row in rows:
        item = dict(row)
        item["item_type"] = classify_faostat_item(item["item_code"], item["crop_name"])
        item["item_type_label"] = item_type_label(item["item_type"])
        if requested_type == "ALL" or item["item_type"] == requested_type:
            items.append(item)
    counts = {kind: sum(x["item_type"] == kind for x in items) for kind in (CROP, AGGREGATE, PRODUCT_FORM)}
    return {
        "source": "FAOSTAT QCL",
        "loaded": bool(items),
        "crop_count": counts[CROP],
        "total_item_count": len(items),
        "item_type_filter": requested_type,
        "item_type_counts": counts,
        "crops": items,
    }


@app.get("/api/v1/global-crops/countries")
def global_crop_countries(crop_code: Optional[str] = None, db: Session = Depends(get_db)):
    params = {}
    where = ""
    if crop_code:
        where = "WHERE crop_code = :crop_code"
        params["crop_code"] = crop_code.strip().upper()
    rows = db.execute(text(f"""
        SELECT country_iso3, MIN(area_name) AS area_name,
               COUNT(*) AS observations, MIN(year) AS first_year,
               MAX(year) AS last_year
        FROM global_crop_statistics
        {where}
        GROUP BY country_iso3
        ORDER BY area_name, country_iso3
    """), params).mappings().all()
    return {"source": "FAOSTAT QCL", "countries": [dict(x) for x in rows]}


@app.get("/api/v1/global-crops/series/{country_iso3}/{crop_code}")
def global_crop_series(
    country_iso3: str,
    crop_code: str,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    db: Session = Depends(get_db),
):
    country = country_iso3.strip().upper()
    crop = crop_code.strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", country):
        raise HTTPException(422, "country_iso3 3 ta harfdan iborat ISO-3 kod bo‘lishi kerak")
    if start_year is not None and end_year is not None and start_year > end_year:
        raise HTTPException(422, "start_year end_year dan katta bo‘lishi mumkin emas")
    conditions = ["country_iso3 = :country", "crop_code = :crop"]
    params = {"country": country, "crop": crop}
    if start_year is not None:
        conditions.append("year >= :start_year")
        params["start_year"] = start_year
    if end_year is not None:
        conditions.append("year <= :end_year")
        params["end_year"] = end_year
    rows = db.execute(text(f"""
        SELECT country_iso3, area_name, crop_code, crop_name, year,
               harvested_area_ha, production_t, yield_t_ha,
               area_flag, production_flag, yield_flag,
               source_code, source_release
        FROM global_crop_statistics
        WHERE {" AND ".join(conditions)}
        ORDER BY year
    """), params).mappings().all()
    return {
        "source": "FAOSTAT QCL",
        "country_iso3": country,
        "crop_code": crop,
        "count": len(rows),
        "series": [dict(row) for row in rows],
    }


@app.post("/api/v1/global-predictions/yield")
def global_yield(payload: GlobalYieldRequest,user: User=Depends(current_user),db: Session=Depends(get_db)):
    from .services.global_crops import forecast_global_crop_yield
    try:
        return forecast_global_crop_yield(db,payload.country_iso3,payload.crop_code,payload.target_year)
    except ValueError as exc:
        raise HTTPException(422,str(exc))

@app.post("/api/v1/predictions")
def prediction(payload: PredictionRequest, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ds = db.scalar(select(Dataset).where(Dataset.id == payload.dataset_id, Dataset.owner_id == user.id))
    if not ds:
        raise HTTPException(404, "Dataset topilmadi")
    obs = db.scalars(select(YieldObservation).where(YieldObservation.dataset_id == ds.id).order_by(YieldObservation.year)).all()
    env = db.scalars(select(EnvironmentFeature).where(EnvironmentFeature.location_id == ds.location_id, EnvironmentFeature.crop_code == ds.crop_code)).all()
    env_map = {x.year: x.features for x in env}
    rows = [{"year": o.year, "yield_t_ha": o.yield_t_ha, **(env_map.get(o.year) or {})} for o in obs]
    try:
        result = evaluate_and_predict(rows, payload.target_year, payload.model)
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    result["dataset_id"] = ds.id
    result["location"] = db.get(Location, ds.location_id).name
    result["crop_code"] = ds.crop_code
    return result
