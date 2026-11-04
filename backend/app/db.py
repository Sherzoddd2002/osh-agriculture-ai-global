from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings


class Base(DeclarativeBase):
    pass


_is_sqlite = settings.database_url.startswith("sqlite:")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=5,
    connect_args=_connect_args,
)

if _is_sqlite:
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    # MVP bootstrap only. Production schema changes must use reviewed migrations.
    from . import models  # noqa: F401

    if settings.enable_postgis:
        if engine.dialect.name != "postgresql":
            raise RuntimeError("ENABLE_POSTGIS=true faqat PostgreSQL serverida ishlaydi.")
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS postgis")

    Base.metadata.create_all(bind=engine)

    if settings.enable_postgis:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE locations ADD COLUMN IF NOT EXISTS geom geometry(Geometry, 4326)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_locations_geom ON locations USING GIST (geom)"))
