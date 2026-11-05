import os
import uuid
from csv import DictReader, DictWriter
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///./tests/osh_agri_sqlite_test.sqlite3")
os.environ.setdefault("ENABLE_POSTGIS", "false")
os.environ.setdefault("JWT_SECRET", "sqlite-integration-test-secret-not-for-production")

from backend.app.db import SessionLocal
from backend.app.import_mapspam_results import (
    read_and_validate_pair,
    upsert_summary_rows,
)
from backend.app.main import app
from backend.app.models import GlobalRasterSummary
from backend.app.services.global_raster_catalog import MAPSPAM_CROPS
from fastapi.testclient import TestClient


CSV_FIELDS = [
    "country_iso3", "country_name", "admin_level", "admin_name", "admin_id",
    "boundary_source", "boundary_year", "dataset_id", "source_year",
    "technology", "crop_code", "crop_name", "crop_band", "physical_area_ha",
    "harvested_area_ha", "production_t", "yield_t_ha_area_weighted",
    "valid_cells", "yield_crosscheck_abs_kg_ha", "spatial_status",
    "computed_at_utc",
]


def _write_pair(
    directory: Path,
    country_iso3: str = "UZB",
    country_name: str = "Uzbekistan",
    zone_count: int = 14,
) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    adm1_path = directory / "adm1.csv"
    adm0_path = directory / "adm0.csv"
    adm1_rows = []
    adm0_rows = []

    for band, (crop_code, crop_name) in enumerate(MAPSPAM_CROPS, 1):
        no_cells = band == len(MAPSPAM_CROPS)
        per_zone = 0.0 if no_cells else 1.0
        yield_value = "" if no_cells else 2.0
        status = "NO_RASTER_CELLS" if no_cells else "ESTIMATED"
        valid_cells = 0 if no_cells else 1

        for zone_number in range(1, zone_count + 1):
            adm1_rows.append({
                "country_iso3": country_iso3,
                "country_name": country_name,
                "admin_level": "ADM1",
                "admin_name": f"Test region {zone_number}",
                "admin_id": f"{country_iso3}-ADM1-{zone_number:02d}",
                "boundary_source": "gbOpen",
                "boundary_year": "2017",
                "dataset_id": "mapspam-2020-v2r2",
                "source_year": "2020",
                "technology": "all",
                "crop_code": crop_code,
                "crop_name": crop_name,
                "crop_band": str(band),
                "physical_area_ha": str(per_zone),
                "harvested_area_ha": str(per_zone),
                "production_t": str(per_zone * 2.0),
                "yield_t_ha_area_weighted": yield_value,
                "valid_cells": str(valid_cells),
                "yield_crosscheck_abs_kg_ha": "" if no_cells else "0",
                "spatial_status": status,
                "computed_at_utc": "2026-11-05T00:00:00+00:00",
            })

        adm0_rows.append({
            "country_iso3": country_iso3,
            "country_name": country_name,
            "admin_level": "ADM0",
            "admin_name": country_name,
            "admin_id": country_iso3,
            "boundary_source": "gbOpen",
            "boundary_year": "2017",
            "dataset_id": "mapspam-2020-v2r2",
            "source_year": "2020",
            "technology": "all",
            "crop_code": crop_code,
            "crop_name": crop_name,
            "crop_band": str(band),
            "physical_area_ha": str(per_zone * zone_count),
            "harvested_area_ha": str(per_zone * zone_count),
            "production_t": str(per_zone * 2.0 * zone_count),
            "yield_t_ha_area_weighted": yield_value,
            "valid_cells": str(valid_cells * zone_count),
            "yield_crosscheck_abs_kg_ha": "" if no_cells else "0",
            "spatial_status": status,
            "computed_at_utc": "2026-11-05T00:00:00+00:00",
        })

    for path, rows in ((adm1_path, adm1_rows), (adm0_path, adm0_rows)):
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = DictWriter(stream, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    return adm1_path, adm0_path


def test_mapspam_pair_validation_checks_coverage_and_conservation(tmp_path):
    adm1_path, adm0_path = _write_pair(tmp_path)
    rows, report = read_and_validate_pair(adm1_path, adm0_path)

    assert report["status"] == "PASS"
    assert report["country_iso3"] == "UZB"
    assert report["adm1_zone_count"] == 14
    assert report["adm1_rows"] == 644
    assert report["adm0_rows"] == 46
    assert len(rows) == 690

    no_cells = next(row for row in rows if row["spatial_status"] == "NO_RASTER_CELLS")
    assert no_cells["yield_t_ha_area_weighted"] is None
    assert no_cells["valid_cells"] == 0


def test_mapspam_import_is_idempotent_on_sqlite(tmp_path):
    adm1_path, adm0_path = _write_pair(tmp_path)
    rows, _ = read_and_validate_pair(adm1_path, adm0_path)

    engine = create_engine("sqlite:///:memory:")
    GlobalRasterSummary.__table__.create(engine)
    with Session(engine) as db:
        first = upsert_summary_rows(db, rows)
        second = upsert_summary_rows(db, rows)
        total = db.scalar(select(func.count()).select_from(GlobalRasterSummary))

    assert first == {"inserted": 690, "updated": 0, "processed": 690}
    assert second == {"inserted": 0, "updated": 690, "processed": 690}
    assert total == 690
    engine.dispose()


def test_mapspam_pair_rejects_non_conserving_country_total(tmp_path):
    adm1_path, adm0_path = _write_pair(tmp_path)
    with adm0_path.open("r", newline="", encoding="utf-8") as stream:
        reader = DictReader(stream)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    # Increase the first national crop production without changing ADM1.
    rows[0]["production_t"] = "999999"
    with adm0_path.open("w", newline="", encoding="utf-8") as stream:
        writer = DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    with pytest.raises(ValueError, match="production_t"):
        read_and_validate_pair(adm1_path, adm0_path)


def _combine_csvs(sources: list[Path], destination: Path) -> Path:
    with destination.open("w", newline="", encoding="utf-8") as stream:
        writer = DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for source in sources:
            with source.open("r", newline="", encoding="utf-8-sig") as incoming:
                writer.writerows(DictReader(incoming))
    return destination


def test_global_mapspam_import_validates_each_country_independently(tmp_path):
    uzb_adm1, uzb_adm0 = _write_pair(
        tmp_path / "uzb", "UZB", "Uzbekistan", zone_count=14
    )
    kaz_adm1, kaz_adm0 = _write_pair(
        tmp_path / "kaz", "KAZ", "Kazakhstan", zone_count=2
    )
    adm1_path = _combine_csvs(
        [uzb_adm1, kaz_adm1], tmp_path / "global_adm1.csv"
    )
    adm0_path = _combine_csvs(
        [uzb_adm0, kaz_adm0], tmp_path / "global_adm0.csv"
    )

    rows, report = read_and_validate_pair(adm1_path, adm0_path)
    assert report["status"] == "PASS"
    assert report["countries_total"] == 2
    assert report["countries_passed"] == ["KAZ", "UZB"]
    assert report["adm1_rows"] == 16 * 46
    assert report["adm0_rows"] == 2 * 46
    assert len(rows) == (16 + 2) * 46

    # Corrupt one Kazakhstan national total. Strict mode must reject the
    # complete batch; partial mode must retain only the independently verified
    # Uzbekistan pair and report Kazakhstan as skipped.
    with adm0_path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = DictReader(stream)
        national_rows = list(reader)
        fields = list(reader.fieldnames or [])
    kaz_wheat = next(
        row for row in national_rows
        if row["country_iso3"] == "KAZ" and row["crop_code"] == "whea"
    )
    kaz_wheat["production_t"] = "999999"
    with adm0_path.open("w", newline="", encoding="utf-8") as stream:
        writer = DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(national_rows)

    with pytest.raises(ValueError, match="KAZ"):
        read_and_validate_pair(adm1_path, adm0_path)

    partial_rows, partial_report = read_and_validate_pair(
        adm1_path, adm0_path, allow_partial_countries=True
    )
    assert partial_report["status"] == "PARTIAL"
    assert partial_report["countries_passed"] == ["UZB"]
    assert partial_report["countries_rejected"] == ["KAZ"]
    assert partial_report["adm1_rows"] == 644
    assert partial_report["adm0_rows"] == 46
    assert len(partial_rows) == 690


def test_global_raster_summaries_api_filters_and_keeps_null_yield():
    marker = f"api-test-{uuid.uuid4().hex}"
    crop_code, crop_name = MAPSPAM_CROPS[0]
    row = GlobalRasterSummary(
        dataset_id=marker,
        country_iso3="UZB",
        country_name="Uzbekistan",
        admin_level="ADM1",
        admin_name="Test API region",
        admin_id="UZB-API-TEST",
        boundary_source="gbOpen",
        boundary_year=2017,
        source_year=2020,
        technology="all",
        crop_code=crop_code,
        crop_name=crop_name,
        crop_band=1,
        physical_area_ha=0.0,
        harvested_area_ha=0.0,
        production_t=0.0,
        yield_t_ha_area_weighted=None,
        valid_cells=0,
        yield_crosscheck_abs_kg_ha=None,
        spatial_status="NO_RASTER_CELLS",
    )
    with TestClient(app) as client:
        with SessionLocal() as db:
            db.add(row)
            db.commit()

        try:
            response = client.get(
                "/api/v1/global-raster-summaries",
                params={
                    "dataset_id": marker,
                    "country_iso3": "UZB",
                    "admin_level": "ADM1",
                    "crop_code": crop_code,
                },
            )
            assert response.status_code == 200, response.text
            payload = response.json()
            assert payload["count"] == 1
            assert payload["returned"] == 1
            assert payload["items"][0]["spatial_status"] == "NO_RASTER_CELLS"
            assert payload["items"][0]["yield_t_ha_area_weighted"] is None
        finally:
            with SessionLocal() as db:
                db.query(GlobalRasterSummary).filter_by(dataset_id=marker).delete()
                db.commit()
