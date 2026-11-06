"""Resumable MAPSPAM runner for ADM2–ADM4 with explicit parent links.

This module is separate from the stable ADM0/ADM1 runner so existing global
jobs and their checkpoints are never changed by the deeper-level rollout.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from shapely.geometry import shape
from shapely.ops import unary_union

from .run_global_mapspam import (
    _checkpoint_key,
    _load_boundary,
    _load_existing_result_keys,
    _save_checkpoint,
    _countries,
)
from .services.global_raster_batch import aggregate_mapspam_zone_all_crops
from .services.global_raster_catalog import MAPSPAM_CROPS, default_global_data_dir


def _feature_zone(feature: dict[str, Any], iso3: str, level: str, index: int) -> dict[str, Any]:
    props = feature.get("properties") or {}
    name = (
        props.get("shapeName")
        or props.get("name")
        or props.get(f"NAME_{int(level[-1])}")
        or props.get(f"name_{int(level[-1])}")
        or "Unknown"
    )
    zone_id = (
        props.get("shapeID")
        or props.get("shapeISO")
        or props.get("shapeID")
        or f"{iso3}-{index}"
    )
    geometry = feature.get("geometry")
    if not geometry:
        raise ValueError(f"{level} feature {index} has no geometry")
    geom = shape(geometry)
    if geom.is_empty or not geom.is_valid:
        raise ValueError(f"{level} feature {index} has empty or invalid geometry")
    if geom.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError(f"{level} feature {index} geometry is not polygonal")
    return {
        "name": str(name),
        "id": str(zone_id),
        "geometry": geometry,
        "_shape": geom,
    }


def _boundary_zones(boundary: dict[str, Any], iso3: str, level: str) -> list[dict[str, Any]]:
    features = boundary["geojson"]["features"]
    if level == "ADM0":
        geometries = [
            shape(feature["geometry"])
            for feature in features
            if feature.get("geometry")
        ]
        if not geometries:
            raise ValueError(f"{iso3} ADM0 boundary has no polygon geometry")
        dissolved = unary_union(geometries)
        return [{
            "name": iso3,
            "id": iso3,
            "geometry": dissolved.__geo_interface__,
            "_shape": dissolved,
        }]

    zones = [
        _feature_zone(feature, iso3, level, index)
        for index, feature in enumerate(features, 1)
        if feature.get("geometry")
    ]
    if not zones:
        raise ValueError(f"{iso3} {level} boundary contains no polygon features")
    ids = [zone["id"] for zone in zones]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{iso3} {level} boundary contains duplicate admin IDs")
    return zones


def _assign_parent_id(child_geometry: dict[str, Any], parent_zones: list[dict[str, Any]]) -> str:
    """Link a child polygon to the parent covering its representative point.

    If boundaries do not nest perfectly, use the parent with the largest
    positive intersection area. A child with no spatial parent is rejected.
    """
    child = shape(child_geometry)
    if child.is_empty or not child.is_valid:
        raise ValueError("Child geometry is empty or invalid")
    point = child.representative_point()
    containing = [
        parent for parent in parent_zones
        if parent["_shape"].covers(point)
    ]
    if len(containing) == 1:
        return containing[0]["id"]
    if len(containing) > 1:
        # Resolve overlaps deterministically using the greatest child overlap.
        containing.sort(
            key=lambda parent: child.intersection(parent["_shape"]).area,
            reverse=True,
        )
        return containing[0]["id"]

    overlaps = [
        (child.intersection(parent["_shape"]).area, parent["id"])
        for parent in parent_zones
        if child.intersects(parent["_shape"])
    ]
    overlaps = [item for item in overlaps if item[0] > 0]
    if not overlaps:
        raise ValueError("Child administrative polygon does not intersect any parent")
    overlaps.sort(key=lambda item: item[0], reverse=True)
    return overlaps[0][1]


def run(args: argparse.Namespace) -> None:
    level = str(args.level).upper()
    try:
        level_number = int(level.replace("ADM", ""))
    except ValueError as exc:
        raise SystemExit("--level must be ADM2, ADM3 or ADM4") from exc
    if level not in {"ADM2", "ADM3", "ADM4"} or level_number not in {2, 3, 4}:
        raise SystemExit("This runner supports ADM2, ADM3 and ADM4.")

    parent_level = f"ADM{level_number - 1}"
    data_dir = Path(args.data_dir or default_global_data_dir()).expanduser()
    output = Path(args.output_dir).expanduser()
    cache = output / "boundary-cache"
    output.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)

    selected = {
        value.strip().upper()
        for value in str(args.countries or "").split(",")
        if value.strip()
    } or None
    countries = [
        (iso3, name) for iso3, name in _countries()
        if selected is None or iso3 in selected
    ]
    if not countries:
        raise SystemExit("No matching ISO3 countries.")

    summary_path = output / f"mapspam_2020_{level.lower()}.csv"
    errors_path = output / f"mapspam_2020_{level.lower()}_errors.csv"
    completed_path = output / f"mapspam_2020_{level.lower()}_completed.json"
    completed = set()
    if args.resume and completed_path.is_file():
        completed = set(json.loads(completed_path.read_text(encoding="utf-8")))
    existing_keys = _load_existing_result_keys(summary_path) if args.resume else set()

    fields = [
        "country_iso3", "country_name", "admin_level", "admin_name", "admin_id",
        "parent_admin_level", "parent_admin_id", "boundary_source", "boundary_year",
        "dataset_id", "source_year", "technology", "crop_code", "crop_name",
        "crop_band", "physical_area_ha", "harvested_area_ha", "production_t",
        "yield_t_ha_area_weighted", "valid_cells",
        "yield_crosscheck_abs_kg_ha", "spatial_status", "computed_at_utc",
    ]
    error_fields = [
        "country_iso3", "country_name", "admin_level", "error", "failed_at_utc",
    ]
    write_header = (
        not summary_path.exists()
        or summary_path.stat().st_size == 0
        or not args.resume
    )
    if write_header:
        summary_path.write_text("", encoding="utf-8")
    if not errors_path.exists() or not args.resume:
        errors_path.write_text("", encoding="utf-8")

    with (
        summary_path.open("a", newline="", encoding="utf-8-sig") as result_file,
        errors_path.open("a", newline="", encoding="utf-8-sig") as error_file,
        httpx.Client(timeout=args.timeout, follow_redirects=True) as client,
    ):
        writer = csv.DictWriter(result_file, fieldnames=fields)
        error_writer = csv.DictWriter(error_file, fieldnames=error_fields)
        if write_header:
            writer.writeheader()
        if errors_path.stat().st_size == 0:
            error_writer.writeheader()

        for index, (iso3, country_name) in enumerate(countries, 1):
            print(f"[{index}/{len(countries)}] {iso3} {country_name}", flush=True)
            try:
                child_boundary, child_source = _load_boundary(
                    client, iso3, level, cache
                )
                parent_boundary, _ = _load_boundary(
                    client, iso3, parent_level, cache
                )
                child_zones = _boundary_zones(child_boundary, iso3, level)
                parent_zones = _boundary_zones(parent_boundary, iso3, parent_level)

                linked_zones = []
                for zone in child_zones:
                    parent_id = _assign_parent_id(zone["geometry"], parent_zones)
                    linked_zones.append({**zone, "parent_id": parent_id})

                metadata = child_boundary.get("metadata") or {}
                done_this_country = 0
                for zone in linked_zones:
                    checkpoint_key = _checkpoint_key(level, iso3, zone["id"])
                    if checkpoint_key in completed:
                        print(f"  SKIP {zone['name']} (already complete)", flush=True)
                        done_this_country += 1
                        continue

                    summaries = aggregate_mapspam_zone_all_crops(
                        zone["geometry"], data_dir, technology=args.technology
                    )
                    if len(summaries) != len(MAPSPAM_CROPS):
                        raise ValueError(
                            f"{zone['id']} returned {len(summaries)} crop rows; "
                            f"expected {len(MAPSPAM_CROPS)}"
                        )
                    for item in summaries:
                        band = int(item["crop_band"])
                        crop_code, crop_name = MAPSPAM_CROPS[band - 1]
                        result_key = (
                            iso3, zone["id"], item["technology"], crop_code
                        )
                        if result_key in existing_keys:
                            continue
                        has_cells = int(item["valid_cells"]) > 0
                        writer.writerow({
                            "country_iso3": iso3,
                            "country_name": country_name,
                            "admin_level": level,
                            "admin_name": zone["name"],
                            "admin_id": zone["id"],
                            "parent_admin_level": parent_level,
                            "parent_admin_id": zone["parent_id"],
                            "boundary_source": child_source,
                            "boundary_year": metadata.get("boundaryYearRepresented"),
                            "dataset_id": item["dataset_id"],
                            "source_year": item["reference_year"],
                            "technology": item["technology"],
                            "crop_code": crop_code,
                            "crop_name": crop_name,
                            "crop_band": band,
                            "physical_area_ha": item["physical_area_ha"],
                            "harvested_area_ha": item["harvested_area_ha"],
                            "production_t": item["production_t"],
                            "yield_t_ha_area_weighted": item["yield_t_ha_area_weighted"],
                            "valid_cells": item["valid_cells"],
                            "yield_crosscheck_abs_kg_ha": item["yield_crosscheck_abs_kg_ha"],
                            "spatial_status": "ESTIMATED" if has_cells else "NO_RASTER_CELLS",
                            "computed_at_utc": datetime.now(timezone.utc).isoformat(),
                        })
                        existing_keys.add(result_key)

                    result_file.flush()
                    completed.add(checkpoint_key)
                    _save_checkpoint(completed_path, completed)
                    done_this_country += 1

                print(
                    f"  PASS: {done_this_country}/{len(child_zones)} zone(s) complete "
                    f"x {len(MAPSPAM_CROPS)} crops",
                    flush=True,
                )
            except Exception as exc:
                error_writer.writerow({
                    "country_iso3": iso3,
                    "country_name": country_name,
                    "admin_level": level,
                    "error": str(exc)[:1000],
                    "failed_at_utc": datetime.now(timezone.utc).isoformat(),
                })
                error_file.flush()
                print(f"  ERROR: {exc}", file=sys.stderr, flush=True)
                time.sleep(args.error_delay)

    print(json.dumps({
        "level": level,
        "parent_level": parent_level,
        "countries_requested": len(countries),
        "admin_zones_completed": len(completed),
        "completed_units": len(completed),
        "results_csv": str(summary_path),
        "errors_csv": str(errors_path),
        "completed_checkpoint": str(completed_path),
        "source": "MAPSPAM 2020 v2r2",
        "crop_count": len(MAPSPAM_CROPS),
        "interpretation": "2020 gridded estimates, not current-year observations",
    }, ensure_ascii=False, indent=2), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resumable MAPSPAM ADM2–ADM4 runner with parent-zone lineage"
    )
    parser.add_argument("--level", required=True, choices=["ADM2", "ADM3", "ADM4"])
    parser.add_argument("--countries", default="", help="Optional comma-separated ISO3 list")
    parser.add_argument("--technology", choices=["all", "irrigated", "rainfed"], default="all")
    parser.add_argument("--data-dir", default=str(default_global_data_dir()))
    parser.add_argument("--output-dir", default="data/global-results")
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--error-delay", type=float, default=0.5)
    parser.add_argument("--resume", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
