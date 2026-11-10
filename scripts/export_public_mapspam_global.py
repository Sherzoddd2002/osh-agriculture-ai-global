"""Export public MAPSPAM administrative summaries as country-level gzip JSON.

This exports only the licensed MAPSPAM 2020 aggregate summaries already stored
in PostgreSQL. It does not export FAOSTAT, user uploads, credentials, or raw
raster pixels. Use this only after verifying the source licence and attribution.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.db import SessionLocal
from app.models import GlobalRasterSummary
from app.services.global_raster_catalog import MAPSPAM_CROPS

DATASET_ID = "mapspam-2020-v2r2"
SOURCE_YEAR = 2020
TECHNOLOGY = "all"
LICENSE = "CC BY-SA 4.0"
SOURCE_URL = "https://doi.org/10.7910/DVN/SWPENT"
ATTRIBUTION = (
    "IFPRI, Global Spatially-Disaggregated Crop Production Statistics "
    "(MAPSPAM) 2020 v2r2; licensed under CC BY-SA 4.0."
)
LEVELS = ("ADM1", "ADM2")
CROP_CODES = {code for code, _ in MAPSPAM_CROPS}
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "docs" / "data" / "mapspam" / "global"


def finite_nonnegative(value: Any, field: str, identity: str, *, nullable: bool = False):
    if value is None:
        if nullable:
            return None
        raise ValueError(f"{identity}: {field} is NULL")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{identity}: {field} is not finite/non-negative")
    return number


def iso3(value: Any) -> str:
    result = str(value or "").strip().upper()
    if not re.fullmatch(r"[A-Z]{3}", result):
        raise ValueError(f"Invalid country ISO3 value: {value!r}")
    return result


def iso_datetime(value: Any) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_country_payload(country: str, rows: list[GlobalRasterSummary]) -> dict:
    if not rows:
        raise ValueError(f"{country}: no MAPSPAM rows")

    country_name = str(rows[0].country_name or country)
    levels: dict[str, dict] = {}
    generated_values: list[str] = []

    for level in LEVELS:
        level_rows = [row for row in rows if row.admin_level == level]
        if not level_rows:
            continue
        areas: dict[str, dict] = {}
        boundary_years: set[int] = set()

        for row in level_rows:
            identity = f"{country}/{level}/{row.admin_id}/{row.crop_code}"
            admin_id = str(row.admin_id or "").strip()
            admin_name = str(row.admin_name or "").strip()
            crop_code = str(row.crop_code or "").strip().lower()
            if not admin_id or not admin_name:
                raise ValueError(f"{identity}: missing admin ID/name")
            if crop_code not in CROP_CODES:
                raise ValueError(f"{identity}: unknown MAPSPAM crop code {crop_code!r}")
            if row.boundary_year is not None:
                boundary_years.add(int(row.boundary_year))

            cells_value = finite_nonnegative(row.valid_cells, "valid_cells", identity)
            if not cells_value.is_integer():
                raise ValueError(f"{identity}: valid_cells must be an integer")
            cells = int(cells_value)
            yield_value = finite_nonnegative(
                row.yield_t_ha_area_weighted, "yield_t_ha_area_weighted",
                identity, nullable=True,
            )
            status = str(row.spatial_status or "").upper()
            if status == "ESTIMATED":
                if cells <= 0 or yield_value is None:
                    raise ValueError(f"{identity}: ESTIMATED requires valid cells and yield")
            elif status == "NO_RASTER_CELLS":
                if cells != 0 or yield_value is not None:
                    raise ValueError(f"{identity}: NO_RASTER_CELLS must preserve NULL yield")
            else:
                raise ValueError(f"{identity}: unsupported spatial status {status!r}")

            area = areas.setdefault(
                admin_id,
                {
                    "name": admin_name,
                    "parent_admin_id": row.parent_admin_id,
                    "boundary_year": int(row.boundary_year) if row.boundary_year is not None else None,
                    "crops": {},
                },
            )
            if area["name"] != admin_name:
                raise ValueError(f"{identity}: conflicting admin names for same ID")
            if crop_code in area["crops"]:
                raise ValueError(f"{identity}: duplicate crop row")

            area["crops"][crop_code] = {
                "physical_area_ha": finite_nonnegative(row.physical_area_ha, "physical_area_ha", identity),
                "harvested_area_ha": finite_nonnegative(row.harvested_area_ha, "harvested_area_ha", identity),
                "production_t": finite_nonnegative(row.production_t, "production_t", identity),
                "yield_t_ha": yield_value,
                "valid_cells": cells,
                "spatial_status": status,
                "yield_crosscheck_abs_kg_ha": finite_nonnegative(
                    row.yield_crosscheck_abs_kg_ha, "yield_crosscheck_abs_kg_ha",
                    identity, nullable=True,
                ),
            }
            stamp = iso_datetime(row.computed_at_utc or row.imported_at)
            if stamp:
                generated_values.append(stamp)

        common_year = next(iter(boundary_years)) if len(boundary_years) == 1 else None
        levels[level] = {
            "boundary_year": common_year,
            "boundary_year_varies": len(boundary_years) > 1,
            "area_count": len(areas),
            "crop_count": len(CROP_CODES),
            "areas": areas,
        }

    return {
        "country_iso3": country,
        "country_name": country_name,
        "dataset_id": DATASET_ID,
        "dataset_name": "IFPRI MAPSPAM 2020 v2r2",
        "source_year": SOURCE_YEAR,
        "technology": TECHNOLOGY,
        "unit": {
            "physical_area": "ha",
            "harvested_area": "ha",
            "production": "tonnes",
            "yield": "tonnes per harvested hectare (t/ha)",
        },
        "spatial_resolution": {
            "arc_minutes": 5,
            "approx_km_at_equator": 9.3,
            "note": "Gridded estimates; not field measurements.",
        },
        "license": LICENSE,
        "attribution": ATTRIBUTION,
        "source_url": SOURCE_URL,
        "generated_at_utc": max(generated_values) if generated_values else None,
        "levels": levels,
    }


def write_gzip_json(path: Path, payload: dict) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    with temporary.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=9, mtime=0) as compressed:
            compressed.write(encoded)
    temporary.replace(path)
    return path.stat().st_size


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--countries", default="", help="Optional comma-separated ISO3 list")
    args = parser.parse_args()

    selected = {iso3(item) for item in args.countries.split(",") if item.strip()}
    statement = (
        select(GlobalRasterSummary)
        .where(
            GlobalRasterSummary.dataset_id == DATASET_ID,
            GlobalRasterSummary.source_year == SOURCE_YEAR,
            GlobalRasterSummary.technology == TECHNOLOGY,
            GlobalRasterSummary.admin_level.in_(LEVELS),
        )
        .order_by(
            GlobalRasterSummary.country_iso3,
            GlobalRasterSummary.admin_level,
            GlobalRasterSummary.admin_id,
            GlobalRasterSummary.crop_code,
        )
    )

    grouped: dict[str, list[GlobalRasterSummary]] = defaultdict(list)
    with SessionLocal() as session:
        for row in session.scalars(statement).yield_per(5000):
            country = iso3(row.country_iso3)
            if selected and country not in selected:
                continue
            grouped[country].append(row)

    if not grouped:
        raise SystemExit("No MAPSPAM 2020 ADM1/ADM2 rows matched the database filters.")

    countries: dict[str, dict] = {}
    total_rows = 0
    total_bytes = 0
    for country, rows in sorted(grouped.items()):
        payload = build_country_payload(country, rows)
        filename = f"{country}.json.gz"
        size = write_gzip_json(args.output_dir / filename, payload)
        total_bytes += size
        total_rows += len(rows)
        countries[country] = {
            "file": filename,
            "country_name": payload["country_name"],
            "row_count": len(rows),
            "levels": {
                level: {
                    "area_count": details["area_count"],
                    "crop_count": details["crop_count"],
                    "boundary_year": details["boundary_year"],
                    "boundary_year_varies": details["boundary_year_varies"],
                }
                for level, details in payload["levels"].items()
            },
            "size_bytes": size,
        }

    manifest = {
        "dataset_id": DATASET_ID,
        "source_year": SOURCE_YEAR,
        "technology": TECHNOLOGY,
        "license": LICENSE,
        "attribution": ATTRIBUTION,
        "source_url": SOURCE_URL,
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "country_count": len(countries),
        "total_summary_rows": total_rows,
        "total_compressed_bytes": total_bytes,
        "countries": countries,
        "notes": [
            "Only verified MAPSPAM ADM1/ADM2 administrative summaries are included.",
            "MAPSPAM 2020 is a single reference-year gridded estimate, not a future forecast.",
            "NO_RASTER_CELLS retains NULL yield; it is never converted to zero.",
            "Use the displayed attribution and retain the CC BY-SA 4.0 licence.",
        ],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = args.output_dir / "manifest.json"
    temporary = manifest_path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(manifest_path)
    print(json.dumps({
        "status": "PASS",
        "output_dir": str(args.output_dir),
        "countries": len(countries),
        "summary_rows": total_rows,
        "compressed_mb": round(total_bytes / (1024 * 1024), 2),
        "manifest": str(manifest_path),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
