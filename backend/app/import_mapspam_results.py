"""Validate and import paired MAPSPAM ADM0/ADM1 CSV summaries into PostgreSQL.

The source rasters remain on disk. This command only persists verified aggregate
rows and is safe to rerun: each dataset/year/country/admin/technology/crop key
is updated in place rather than duplicated.

Example:
  python -m app.import_mapspam_results --adm1-csv results/adm1.csv --adm0-csv results/adm0.csv --dry-run
  python -m app.import_mapspam_results --adm1-csv results/adm1.csv --adm0-csv results/adm0.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import SessionLocal, init_db
from .models import GlobalRasterSummary
from .services.global_raster_catalog import MAPSPAM_CROPS


SUM_FIELDS = ("physical_area_ha", "harvested_area_ha", "production_t")
MAX_RELATIVE_SUM_DIFFERENCE = 0.01
MAX_YIELD_DIFFERENCE_T_HA = 0.05
EXPECTED_CROPS = {code for code, _ in MAPSPAM_CROPS}
REQUIRED_COLUMNS = {
    "country_iso3", "country_name", "admin_level", "admin_name", "admin_id",
    "boundary_source", "boundary_year", "dataset_id", "source_year",
    "technology", "crop_code", "crop_name", "crop_band", "physical_area_ha",
    "harvested_area_ha", "production_t", "yield_t_ha_area_weighted",
    "valid_cells", "yield_crosscheck_abs_kg_ha", "spatial_status",
    "computed_at_utc",
}
KEY_FIELDS = (
    "dataset_id", "source_year", "country_iso3", "admin_level",
    "admin_id", "technology", "crop_code",
)


def _required_text(row: dict[str, str], field: str, identity: str) -> str:
    value = (row.get(field) or "").strip()
    if not value:
        raise ValueError(f"{identity}: required field {field} is empty")
    return value


def _number(
    row: dict[str, str],
    field: str,
    identity: str,
    *,
    nullable: bool = False,
    integer: bool = False,
) -> float | int | None:
    raw = (row.get(field) or "").strip()
    if not raw:
        if nullable:
            return None
        raise ValueError(f"{identity}: required numeric field {field} is empty")
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{identity}: invalid {field} value {raw!r}") from exc
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{identity}: {field} must be finite and non-negative")
    if integer:
        if not value.is_integer():
            raise ValueError(f"{identity}: {field} must be an integer")
        return int(value)
    return value


def _datetime_utc(raw: str, identity: str) -> datetime | None:
    value = (raw or "").strip()
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{identity}: invalid computed_at_utc {value!r}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _read_level(path: str | Path, expected_level: str) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"MAPSPAM {expected_level} CSV not found: {source}")

    with source.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        headers = set(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - headers)
        if missing:
            raise ValueError(
                f"{source.name}: missing required columns: {', '.join(missing)}"
            )

        output: list[dict[str, Any]] = []
        identities: set[tuple[str, ...]] = set()
        for line_number, raw in enumerate(reader, 2):
            identity = f"{source.name}:{line_number}"
            country = _required_text(raw, "country_iso3", identity).upper()
            if not re.fullmatch(r"[A-Z]{3}", country):
                raise ValueError(f"{identity}: invalid ISO3 country code {country!r}")
            level = _required_text(raw, "admin_level", identity).upper()
            if level != expected_level:
                raise ValueError(
                    f"{identity}: expected {expected_level}, received {level}"
                )

            dataset_id = _required_text(raw, "dataset_id", identity)
            if dataset_id != "mapspam-2020-v2r2":
                raise ValueError(f"{identity}: unsupported MAPSPAM dataset {dataset_id!r}")
            source_year = int(_number(raw, "source_year", identity, integer=True))
            if source_year != 2020:
                raise ValueError(f"{identity}: expected MAPSPAM reference year 2020")
            technology = _required_text(raw, "technology", identity).lower()
            if technology not in {"all", "irrigated", "rainfed"}:
                raise ValueError(f"{identity}: unsupported technology {technology!r}")

            crop_code = _required_text(raw, "crop_code", identity).lower()
            if crop_code not in EXPECTED_CROPS:
                raise ValueError(f"{identity}: unknown MAPSPAM crop code {crop_code!r}")
            crop_band = int(_number(raw, "crop_band", identity, integer=True))
            expected_band = next(
                (band for band, (code, _) in enumerate(MAPSPAM_CROPS, 1)
                 if code == crop_code),
                None,
            )
            if crop_band != expected_band:
                raise ValueError(
                    f"{identity}: crop band {crop_band} does not match "
                    f"{crop_code} catalog band {expected_band}"
                )

            admin_id = _required_text(raw, "admin_id", identity)
            admin_name = _required_text(raw, "admin_name", identity)
            spatial_status = _required_text(raw, "spatial_status", identity)
            valid_cells = int(_number(raw, "valid_cells", identity, integer=True))
            if spatial_status not in {"ESTIMATED", "NO_RASTER_CELLS"}:
                raise ValueError(
                    f"{identity}: unsupported spatial_status {spatial_status!r}"
                )
            if spatial_status == "ESTIMATED" and valid_cells <= 0:
                raise ValueError(f"{identity}: ESTIMATED row has no raster cells")
            if spatial_status == "NO_RASTER_CELLS" and valid_cells != 0:
                raise ValueError(f"{identity}: NO_RASTER_CELLS row has valid cells")

            row: dict[str, Any] = {
                "dataset_id": dataset_id,
                "country_iso3": country,
                "country_name": _required_text(raw, "country_name", identity),
                "admin_level": level,
                "admin_name": admin_name,
                "admin_id": admin_id,
                "boundary_source": (raw.get("boundary_source") or "").strip() or None,
                "boundary_year": (
                    int(_number(raw, "boundary_year", identity, integer=True))
                    if (raw.get("boundary_year") or "").strip() else None
                ),
                "source_year": source_year,
                "technology": technology,
                "crop_code": crop_code,
                "crop_name": _required_text(raw, "crop_name", identity),
                "crop_band": crop_band,
                "physical_area_ha": _number(raw, "physical_area_ha", identity),
                "harvested_area_ha": _number(raw, "harvested_area_ha", identity),
                "production_t": _number(raw, "production_t", identity),
                "yield_t_ha_area_weighted": _number(
                    raw, "yield_t_ha_area_weighted", identity, nullable=True
                ),
                "valid_cells": valid_cells,
                "yield_crosscheck_abs_kg_ha": _number(
                    raw, "yield_crosscheck_abs_kg_ha", identity, nullable=True
                ),
                "spatial_status": spatial_status,
                "computed_at_utc": _datetime_utc(
                    raw.get("computed_at_utc", ""), identity
                ),
            }
            key = tuple(str(row[field]) for field in KEY_FIELDS)
            if key in identities:
                raise ValueError(f"{identity}: duplicate row identity {key!r}")
            identities.add(key)
            output.append(row)

    if not output:
        raise ValueError(f"{source.name}: CSV contains no result rows")
    return output


def _relative_difference(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), 1e-9)


def validate_adm0_adm1_pair(
    adm1_rows: list[dict[str, Any]],
    adm0_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Check crop coverage and regional-to-country conservation before import."""
    metadata_fields = ("country_iso3", "dataset_id", "source_year", "technology")
    for field in metadata_fields:
        adm1_values = {str(row[field]) for row in adm1_rows}
        adm0_values = {str(row[field]) for row in adm0_rows}
        if len(adm1_values) != 1 or adm1_values != adm0_values:
            raise ValueError(
                f"ADM0/ADM1 mismatch for {field}: ADM1={sorted(adm1_values)}, "
                f"ADM0={sorted(adm0_values)}"
            )

    if {row["admin_level"] for row in adm1_rows} != {"ADM1"}:
        raise ValueError("ADM1 input contains an unexpected admin level")
    if {row["admin_level"] for row in adm0_rows} != {"ADM0"}:
        raise ValueError("ADM0 input contains an unexpected admin level")

    if len(EXPECTED_CROPS) != 46:
        raise ValueError(f"Project MAPSPAM catalog must contain 46 crops, found {len(EXPECTED_CROPS)}")

    zone_crops: dict[str, set[str]] = defaultdict(set)
    zone_names: dict[str, str] = {}
    by_crop: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in adm1_rows:
        zone_id = row["admin_id"]
        previous_name = zone_names.setdefault(zone_id, row["admin_name"])
        if previous_name != row["admin_name"]:
            raise ValueError(f"ADM1 zone {zone_id} has inconsistent names")
        zone_crops[zone_id].add(row["crop_code"])
        by_crop[row["crop_code"]].append(row)

    if not zone_crops:
        raise ValueError("ADM1 input contains no administrative zones")
    incomplete = {
        zone_id: sorted(EXPECTED_CROPS - crops)
        for zone_id, crops in zone_crops.items()
        if crops != EXPECTED_CROPS
    }
    if incomplete:
        raise ValueError(f"ADM1 zones do not each contain all 46 crops: {incomplete}")
    if set(by_crop) != EXPECTED_CROPS:
        raise ValueError("ADM1 input does not contain the complete 46-crop catalog")

    national: dict[str, dict[str, Any]] = {}
    for row in adm0_rows:
        crop = row["crop_code"]
        if crop in national:
            raise ValueError(f"ADM0 input contains duplicate crop row {crop}")
        national[crop] = row
    if set(national) != EXPECTED_CROPS or len(adm0_rows) != 46:
        raise ValueError("ADM0 input must contain exactly one row for each of 46 crops")

    max_relative = {field: 0.0 for field in SUM_FIELDS}
    max_yield_difference = 0.0
    for crop in EXPECTED_CROPS:
        regional_rows = by_crop[crop]
        country_row = national[crop]
        for field in SUM_FIELDS:
            regional_total = sum(float(row[field]) for row in regional_rows)
            country_total = float(country_row[field])
            difference = _relative_difference(regional_total, country_total)
            max_relative[field] = max(max_relative[field], difference)
            if difference > MAX_RELATIVE_SUM_DIFFERENCE:
                raise ValueError(
                    f"{crop} {field} ADM1/ADM0 relative difference "
                    f"{difference:.6%} exceeds 1%"
                )

        regional_area = sum(float(row["harvested_area_ha"]) for row in regional_rows)
        regional_yield_numerator = sum(
            float(row["yield_t_ha_area_weighted"] or 0.0)
            * float(row["harvested_area_ha"])
            for row in regional_rows
        )
        regional_yield = (
            regional_yield_numerator / regional_area if regional_area > 0 else None
        )
        country_yield = country_row["yield_t_ha_area_weighted"]
        if regional_yield is None and country_yield is None:
            yield_difference = 0.0
        elif regional_yield is None or country_yield is None:
            yield_difference = float("inf")
        else:
            yield_difference = abs(regional_yield - float(country_yield))
        if yield_difference > MAX_YIELD_DIFFERENCE_T_HA:
            raise ValueError(
                f"{crop} weighted yield ADM1/ADM0 difference "
                f"{yield_difference:.6f} t/ha exceeds 0.05 t/ha"
            )
        if math.isfinite(yield_difference):
            max_yield_difference = max(max_yield_difference, yield_difference)

    return {
        "status": "PASS",
        "country_iso3": adm1_rows[0]["country_iso3"],
        "dataset_id": adm1_rows[0]["dataset_id"],
        "source_year": adm1_rows[0]["source_year"],
        "technology": adm1_rows[0]["technology"],
        "adm1_zone_count": len(zone_crops),
        "adm1_rows": len(adm1_rows),
        "adm0_rows": len(adm0_rows),
        "crop_count": len(EXPECTED_CROPS),
        "max_relative_differences": max_relative,
        "max_weighted_yield_difference_t_ha": max_yield_difference,
    }


def read_and_validate_pair(
    adm1_path: str | Path,
    adm0_path: str | Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    adm1_rows = _read_level(adm1_path, "ADM1")
    adm0_rows = _read_level(adm0_path, "ADM0")
    report = validate_adm0_adm1_pair(adm1_rows, adm0_rows)
    return adm1_rows + adm0_rows, report


def upsert_summary_rows(
    db: Session,
    rows: list[dict[str, Any]],
) -> dict[str, int]:
    """Insert new summary identities and update existing ones in one transaction."""
    inserted = 0
    updated = 0
    now = datetime.now(timezone.utc)
    try:
        for row in rows:
            key_filter = {
                field: row[field] for field in KEY_FIELDS
            }
            existing = db.scalar(
                select(GlobalRasterSummary).filter_by(**key_filter)
            )
            if existing is None:
                db.add(GlobalRasterSummary(**row, imported_at=now))
                inserted += 1
            else:
                for field, value in row.items():
                    setattr(existing, field, value)
                existing.imported_at = now
                updated += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"inserted": inserted, "updated": updated, "processed": len(rows)}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and import verified MAPSPAM ADM0/ADM1 summaries"
    )
    parser.add_argument("--adm1-csv", required=True, help="Verified ADM1 results CSV")
    parser.add_argument("--adm0-csv", required=True, help="Official ADM0 totals CSV")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate source files and ADM0/ADM1 conservation without database writes",
    )
    args = parser.parse_args()

    rows, report = read_and_validate_pair(args.adm1_csv, args.adm0_csv)
    result: dict[str, Any] = {"validation": report}
    if args.dry_run:
        result["database_write"] = "SKIPPED (dry-run)"
    else:
        init_db()
        with SessionLocal() as db:
            result["database"] = upsert_summary_rows(db, rows)
        result["database_write"] = "COMMITTED"

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
