from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


def utcnow():
    return datetime.now(timezone.utc)


def json_payload_type():
    # SQLite uses JSON; PostgreSQL keeps the more capable JSONB storage.
    return JSON().with_variant(JSONB(), "postgresql")


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    datasets = relationship("Dataset", back_populates="owner")


class Location(Base):
    __tablename__ = "locations"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    country_iso3: Mapped[str] = mapped_column(String(3), index=True)
    name: Mapped[str] = mapped_column(String(250))
    admin_level: Mapped[str] = mapped_column(String(8), default="ADM1")
    centroid_lat: Mapped[float] = mapped_column(Float)
    centroid_lon: Mapped[float] = mapped_column(Float)
    geojson: Mapped[dict] = mapped_column(json_payload_type())
    source: Mapped[str] = mapped_column(String(80), default="geoBoundaries")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    datasets = relationship("Dataset", back_populates="location")


class Dataset(Base):
    __tablename__ = "datasets"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(250))
    crop_code: Mapped[str] = mapped_column(String(40), index=True)
    area_basis: Mapped[str] = mapped_column(String(30), default="unknown")
    season_start: Mapped[str] = mapped_column(String(5), default="10-01")
    season_end: Mapped[str] = mapped_column(String(5), default="06-30")
    global_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    source_sha256: Mapped[str] = mapped_column(String(64))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    first_year: Mapped[int] = mapped_column(Integer)
    last_year: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="UPLOADED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    owner = relationship("User", back_populates="datasets")
    location = relationship("Location", back_populates="datasets")
    observations = relationship("YieldObservation", back_populates="dataset", cascade="all, delete-orphan")


class YieldObservation(Base):
    __tablename__ = "yield_observations"
    __table_args__ = (UniqueConstraint("dataset_id", "year", name="uq_dataset_year"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    yield_t_ha: Mapped[float] = mapped_column(Float)
    area_ha: Mapped[float | None] = mapped_column(Float, nullable=True)
    production_t: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_status: Mapped[str] = mapped_column(String(24), default="OBSERVED")
    dataset = relationship("Dataset", back_populates="observations")


class EnvironmentFeature(Base):
    __tablename__ = "environment_features"
    __table_args__ = (UniqueConstraint("location_id", "crop_code", "year", name="uq_location_crop_year"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), index=True)
    crop_code: Mapped[str] = mapped_column(String(40), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    features: Mapped[dict] = mapped_column(json_payload_type())
    source_status: Mapped[dict] = mapped_column(json_payload_type())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    job_type: Mapped[str] = mapped_column(String(40), default="ENVIRONMENT_ENRICHMENT")
    status: Mapped[str] = mapped_column(String(20), default="QUEUED", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="Navbatda")
    result: Mapped[dict | None] = mapped_column(json_payload_type(), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class LocationClimateJob(Base):
    """Annual climate and short-range weather job; independent of crop-yield datasets."""
    __tablename__ = "location_climate_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), index=True)
    start_year: Mapped[int] = mapped_column(Integer, default=2010)
    end_year: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="QUEUED", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="Navbatda")
    result: Mapped[dict | None] = mapped_column(json_payload_type(), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LocationWeatherSnapshot(Base):
    """Latest current/short-range forecast snapshot for a saved location."""
    __tablename__ = "location_weather_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"), unique=True, index=True)
    payload: Mapped[dict] = mapped_column(json_payload_type())
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)



class GlobalCropStatistic(Base):
    __tablename__ = "global_crop_statistics"
    __table_args__ = (UniqueConstraint("source_code","area_m49","item_code","year",name="uq_global_crop_source_area_item_year"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source_code: Mapped[str] = mapped_column(String(24),default="FAOSTAT_QCL",index=True)
    source_release: Mapped[str] = mapped_column(String(32),default="")
    area_m49: Mapped[str] = mapped_column(String(3),index=True)
    country_iso3: Mapped[str] = mapped_column(String(3),index=True)
    area_name: Mapped[str] = mapped_column(String(160))
    item_code: Mapped[str] = mapped_column(String(32))
    crop_code: Mapped[str] = mapped_column(String(64),index=True)
    crop_name: Mapped[str] = mapped_column(String(160))
    year: Mapped[int] = mapped_column(Integer,index=True)
    harvested_area_ha: Mapped[float|None] = mapped_column(Float,nullable=True)
    production_t: Mapped[float|None] = mapped_column(Float,nullable=True)
    yield_t_ha: Mapped[float|None] = mapped_column(Float,nullable=True)
    area_flag: Mapped[str|None] = mapped_column(String(32),nullable=True)
    production_flag: Mapped[str|None] = mapped_column(String(32),nullable=True)
    yield_flag: Mapped[str|None] = mapped_column(String(32),nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=utcnow)

class GlobalRasterSummary(Base):
    """Persisted administrative summary rows derived from official global rasters."""
    __tablename__ = "global_raster_summaries"
    __table_args__ = (
        UniqueConstraint(
            "dataset_id", "source_year", "country_iso3", "admin_level",
            "admin_id", "technology", "crop_code",
            name="uq_global_raster_summary_identity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(80), index=True)
    country_iso3: Mapped[str] = mapped_column(String(3), index=True)
    country_name: Mapped[str] = mapped_column(String(160))
    admin_level: Mapped[str] = mapped_column(String(8), index=True)
    admin_name: Mapped[str] = mapped_column(String(250))
    admin_id: Mapped[str] = mapped_column(String(250))
    parent_admin_level: Mapped[str | None] = mapped_column(String(8), nullable=True, index=True)
    parent_admin_id: Mapped[str | None] = mapped_column(String(250), nullable=True, index=True)
    parent_boundary_source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    parent_boundary_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parent_link_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    parent_link_distance_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    hierarchy_validation_status: Mapped[str] = mapped_column(String(64), default="NOT_CHECKED", index=True)
    boundary_source: Mapped[str | None] = mapped_column(String(80), nullable=True)
    boundary_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_year: Mapped[int] = mapped_column(Integer, index=True)
    technology: Mapped[str] = mapped_column(String(16), default="all")
    crop_code: Mapped[str] = mapped_column(String(40), index=True)
    crop_name: Mapped[str] = mapped_column(String(160))
    crop_band: Mapped[int] = mapped_column(Integer)
    physical_area_ha: Mapped[float] = mapped_column(Float)
    harvested_area_ha: Mapped[float] = mapped_column(Float)
    production_t: Mapped[float] = mapped_column(Float)
    yield_t_ha_area_weighted: Mapped[float | None] = mapped_column(Float, nullable=True)
    valid_cells: Mapped[int] = mapped_column(Integer)
    yield_crosscheck_abs_kg_ha: Mapped[float | None] = mapped_column(Float, nullable=True)
    spatial_status: Mapped[str] = mapped_column(String(24), index=True)
    computed_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

