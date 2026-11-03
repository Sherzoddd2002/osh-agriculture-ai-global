from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=5,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    # MVP bootstrap only. Production schema changes must use reviewed migrations.
    from . import models  # noqa: F401
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS postgis")
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE locations ADD COLUMN IF NOT EXISTS geom geometry(Geometry, 4326)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_locations_geom ON locations USING GIST (geom)"))
