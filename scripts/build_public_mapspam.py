"""Publish the validated Uzbekistan MAPSPAM 2020 ADM1/ADM2 summaries.

The input is the artifact produced by the real-data MAPSPAM Actions workflow.
Every admin/crop identity is checked against the exact public GeoJSON bundle
before a small, browser-readable JSON file is created for GitHub Pages.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_ZONES = {"ADM1": 14, "ADM2": 199}
EXPECTED_BOUNDARY_YEARS = {"ADM1": "2017", "ADM2": "2020"}
DATASET_ID = "mapspam-2020-v2r2"
SOURCE_YEAR = "2020"
TECHNOLOGY = "all"
MAPSPAM_LICENSE = "CC BY-SA 4.0"
SOURCE_URL = "https://doi.org/10.7910/DVN/SWPENT"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise SystemExit(f"FAIL: required MAPSPAM CSV is missing: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise SystemExit(f"FAIL: MAPSPAM CSV has no header: {path}")
        return list(reader)


def read_errors(path: Path) -> None:
    rows = read_csv(path)
    if rows:
        raise SystemExit(
            f"FAIL: MAPSPAM artifact contains errors in {path.name}: "
            + json.dumps(rows[:5], ensure_ascii=False)
        )


def numeric(row: dict[str, str], column: str, identity: str, *, nullable: bool = False):
    raw = (row.get(column) or "").strip()
    if not raw:
        if nullable:
            return None
        raise SystemExit(f"FAIL: {identity} has blank {column}")
    try:
        value = float(raw)
    except ValueError as exc:
        raise SystemExit(f"FAIL: {identity} has invalid {column}: {raw!r}") from exc
    if not math.isfinite(value) or value < 0:
        raise SystemExit(f"FAIL: {identity} has out-of-range {column}: {raw!r}")
    return value


def load_crop_catalog(html_path: Path) -> dict[str, str]:
    html = html_path.read_text(encoding="utf-8")
    match = re.search(r"const cropList=\[(.*?)\n\s*\];", html, flags=re.DOTALL)
    if not match:
        raise SystemExit("FAIL: website MAPSPAM crop catalogue was not found")
    pairs = re.findall(r'\["([a-z]{4})","([^"]+)"\]', match.group(1))
    catalog = dict(pairs)
    if len(catalog) != 46 or len(pairs) != 46:
        raise SystemExit(
            f"FAIL: website must contain 46 unique MAPSPAM crops; found {len(pairs)}"
        )
    return catalog


def load_boundary_index(boundaries_dir: Path, level: str) -> tuple[dict[str, str], dict[str, Any]]:
    path = boundaries_dir / f"UZB_{level}.geojson"
    if not path.is_file():
        raise SystemExit(f"FAIL: public {level} GeoJSON is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("type") != "FeatureCollection":
        raise SystemExit(f"FAIL: public {level} boundary is not a FeatureCollection")
    metadata = payload.get("metadata") or {}
    if metadata.get("country_iso3") != "UZB" or metadata.get("admin_level") != level:
        raise SystemExit(f"FAIL: public {level} boundary metadata is not UZB {level}")
    if str(metadata.get("boundary_year")) != EXPECTED_BOUNDARY_YEARS[level]:
        raise SystemExit(
            f"FAIL: public {level} boundary vintage changed: "
            f"{metadata.get('boundary_year')!r}"
        )

    index: dict[str, str] = {}
    for feature in payload.get("features", []):
        props = feature.get("properties") or {}
        shape_id = str(props.get("shapeID") or "").strip()
        shape_name = str(props.get("shapeName") or "").strip()
        if not shape_id or not shape_name:
            raise SystemExit(f"FAIL: public {level} feature has no shapeID/shapeName")
        if shape_id in index:
            raise SystemExit(f"FAIL: duplicate shapeID in public {level}: {shape_id}")
        index[shape_id] = shape_name
    if len(index) != EXPECTED_ZONES[level]:
        raise SystemExit(
            f"FAIL: public {level} must have {EXPECTED_ZONES[level]} unique IDs; "
            f"found {len(index)}"
        )
    return index, metadata


def build_level(
    rows: list[dict[str, str]],
    level: str,
    crop_catalog: dict[str, str],
    boundary_index: dict[str, str],
) -> dict[str, Any]:
    expected_year = EXPECTED_BOUNDARY_YEARS[level]
    expected_pairs = EXPECTED_ZONES[level] * len(crop_catalog)
    if len(rows) != expected_pairs:
        raise SystemExit(
            f"FAIL: {level} must contain {expected_pairs} rows "
            f"({EXPECTED_ZONES[level]} areas x 46 crops); found {len(rows)}"
        )

    areas: dict[str, dict[str, Any]] = {}
    seen: set[tuple[str, str]] = set()
    for row_number, row in enumerate(rows, 2):
        identity = f"{level} CSV line {row_number}"
        required_identity = {
            "country_iso3": "UZB",
            "admin_level": level,
            "dataset_id": DATASET_ID,
            "source_year": SOURCE_YEAR,
            "technology": TECHNOLOGY,
            "boundary_source": "gbOpen",
            "boundary_year": expected_year,
        }
        for field, expected in required_identity.items():
            if row.get(field) != expected:
                raise SystemExit(
                    f"FAIL: {identity} {field}={row.get(field)!r}; expected {expected!r}"
                )

        area_id = (row.get("admin_id") or "").strip()
        area_name = (row.get("admin_name") or "").strip()
        crop_code = (row.get("crop_code") or "").strip()
        if area_id not in boundary_index:
            raise SystemExit(
                f"FAIL: {identity} admin_id {area_id!r} is not present in public {level} GeoJSON"
            )
        if boundary_index[area_id] != area_name:
            raise SystemExit(
                f"FAIL: {identity} name {area_name!r} does not match boundary "
                f"name {boundary_index[area_id]!r}"
            )
        if crop_code not in crop_catalog:
            raise SystemExit(f"FAIL: {identity} unknown crop code {crop_code!r}")
        if (area_id, crop_code) in seen:
            raise SystemExit(f"FAIL: {identity} duplicate area/crop identity")
        seen.add((area_id, crop_code))

        if row.get("crop_name") != crop_catalog[crop_code]:
            raise SystemExit(
                f"FAIL: {identity} crop label does not match the website catalogue"
            )
        if not area_id or not area_name:
            raise SystemExit(f"FAIL: {identity} has an empty area identity")

        physical = numeric(row, "physical_area_ha", identity)
        harvested = numeric(row, "harvested_area_ha", identity)
        production = numeric(row, "production_t", identity)
        valid_cells_value = numeric(row, "valid_cells", identity)
        if not valid_cells_value.is_integer():
            raise SystemExit(f"FAIL: {identity} valid_cells is not an integer")
        valid_cells = int(valid_cells_value)
        weighted_yield = numeric(
            row, "yield_t_ha_area_weighted", identity, nullable=True
        )
        crosscheck = numeric(
            row, "yield_crosscheck_abs_kg_ha", identity, nullable=True
        )
        status = row.get("spatial_status")
        if status == "ESTIMATED":
            if valid_cells <= 0 or weighted_yield is None:
                raise SystemExit(
                    f"FAIL: {identity} is ESTIMATED without valid raster cells and yield"
                )
        elif status == "NO_RASTER_CELLS":
            if valid_cells != 0 or weighted_yield is not None:
                raise SystemExit(
                    f"FAIL: {identity} NO_RASTER_CELLS must retain zero cells "
                    "and NULL yield, never a fabricated zero yield"
                )
        else:
            raise SystemExit(f"FAIL: {identity} unknown spatial_status {status!r}")

        if level == "ADM1":
            parent_id = None
        else:
            if row.get("parent_admin_level") != "ADM1":
                raise SystemExit(f"FAIL: {identity} has no ADM1 parent level")
            parent_id = (row.get("parent_admin_id") or "").strip()
            if not parent_id:
                raise SystemExit(f"FAIL: {identity} has no parent_admin_id")

        area = areas.setdefault(
            area_id,
            {
                "name": area_name,
                "parent_admin_id": parent_id,
                "crops": {},
            },
        )
        if area["name"] != area_name or area["parent_admin_id"] != parent_id:
            raise SystemExit(f"FAIL: {identity} has inconsistent area metadata")

        area["crops"][crop_code] = {
            "physical_area_ha": physical,
            "harvested_area_ha": harvested,
            "production_t": production,
            "yield_t_ha": weighted_yield,
            "valid_cells": valid_cells,
            "spatial_status": status,
            "yield_crosscheck_abs_kg_ha": crosscheck,
        }

    if set(areas) != set(boundary_index):
        missing = sorted(set(boundary_index) - set(areas))
        extra = sorted(set(areas) - set(boundary_index))
        raise SystemExit(
            f"FAIL: {level} area identities do not match GeoJSON; "
            f"missing={missing[:5]}, extra={extra[:5]}"
        )
    for area_id, area in areas.items():
        codes = set(area["crops"])
        if codes != set(crop_catalog):
            raise SystemExit(
                f"FAIL: {level} {area['name']} is missing crop rows: "
                f"{sorted(set(crop_catalog) - codes)}"
            )

    return {
        "boundary_year": int(expected_year),
        "boundary_id": None,
        "area_count": len(areas),
        "crop_count": len(crop_catalog),
        "areas": areas,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--boundaries-dir", type=Path, required=True)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    adm1_dir = args.input_dir / ".ci-mapspam-output"
    adm2_dir = args.input_dir / ".ci-mapspam-adm2-output"
    adm1_csv = adm1_dir / "mapspam_2020_adm1.csv"
    adm2_csv = adm2_dir / "mapspam_2020_adm2.csv"
    read_errors(adm1_dir / "mapspam_2020_adm1_errors.csv")
    read_errors(adm2_dir / "mapspam_2020_adm2_errors.csv")
    read_errors(args.input_dir / ".ci-mapspam-adm0-output" / "mapspam_2020_adm0_errors.csv")

    crop_catalog = load_crop_catalog(args.html)
    adm1_index, adm1_meta = load_boundary_index(args.boundaries_dir, "ADM1")
    adm2_index, adm2_meta = load_boundary_index(args.boundaries_dir, "ADM2")

    adm1_rows = read_csv(adm1_csv)
    adm2_rows = read_csv(adm2_csv)
    adm1 = build_level(adm1_rows, "ADM1", crop_catalog, adm1_index)
    adm2 = build_level(adm2_rows, "ADM2", crop_catalog, adm2_index)

    parent_ids = {
        area["parent_admin_id"] for area in adm2["areas"].values()
    }
    if parent_ids != set(adm1["areas"]):
        raise SystemExit(
            "FAIL: ADM2 parent IDs do not exactly match the published ADM1 areas; "
            f"missing={sorted(set(adm1['areas']) - parent_ids)}, "
            f"unknown={sorted(parent_ids - set(adm1['areas']))}"
        )
    for area_id, area in adm2["areas"].items():
        if area["parent_admin_id"] not in adm1["areas"]:
            raise SystemExit(f"FAIL: ADM2 {area['name']} has an unknown ADM1 parent")

    adm1["boundary_id"] = adm1_meta.get("boundary_id")
    adm2["boundary_id"] = adm2_meta.get("boundary_id")

    output = {
        "country_iso3": "UZB",
        "dataset_id": DATASET_ID,
        "dataset_name": "IFPRI MAPSPAM 2020 v2r2",
        "source_year": 2020,
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
        "license": MAPSPAM_LICENSE,
        "attribution": (
            "IFPRI, Global Spatially-Disaggregated Crop Production Statistics "
            "(MAPSPAM) 2020 v2r2; CC BY-SA 4.0."
        ),
        "source_url": SOURCE_URL,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "boundary_sources": {
            "ADM1": {
                "source": adm1_meta.get("source"),
                "source_url": adm1_meta.get("source_url"),
                "boundary_year": adm1_meta.get("boundary_year"),
                "license": adm1_meta.get("license"),
                "boundary_id": adm1_meta.get("boundary_id"),
            },
            "ADM2": {
                "source": adm2_meta.get("source"),
                "source_url": adm2_meta.get("source_url"),
                "boundary_year": adm2_meta.get("boundary_year"),
                "license": adm2_meta.get("license"),
                "boundary_id": adm2_meta.get("boundary_id"),
            },
        },
        "levels": {"ADM1": adm1, "ADM2": adm2},
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp_path = args.output.with_suffix(args.output.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(output, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    temp_path.replace(args.output)

    print(json.dumps({
        "status": "PASS",
        "output": str(args.output),
        "size_bytes": args.output.stat().st_size,
        "ADM1_areas": adm1["area_count"],
        "ADM1_rows": len(adm1_rows),
        "ADM2_areas": adm2["area_count"],
        "ADM2_rows": len(adm2_rows),
        "crops": len(crop_catalog),
        "ADM2_parent_provinces": len(parent_ids),
        "NO_RASTER_CELLS_ADM1": sum(
            crop["spatial_status"] == "NO_RASTER_CELLS"
            for area in adm1["areas"].values() for crop in area["crops"].values()
        ),
        "NO_RASTER_CELLS_ADM2": sum(
            crop["spatial_status"] == "NO_RASTER_CELLS"
            for area in adm2["areas"].values() for crop in area["crops"].values()
        ),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
