"""Resumable global MAPSPAM country x crop batch.

Example:
  python -m app.run_global_mapspam --level ADM0
  python -m app.run_global_mapspam --level ADM0 --countries UZB,KAZ,TUR
  python -m app.run_global_mapspam --level ADM1 --countries UZB
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pycountry
from shapely.geometry import shape
from shapely.ops import unary_union

from .services.global_raster_batch import aggregate_mapspam_zone_all_crops
from .services.global_raster_catalog import MAPSPAM_CROPS, default_global_data_dir


def _safe_name(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in value)


def _load_boundary(client: httpx.Client, iso3: str, level: str, cache: Path):
    cache_file = cache / f"{iso3}_{level}.geojson"
    if cache_file.is_file():
        return json.loads(cache_file.read_text(encoding="utf-8")), "cache"

    errors = []
    for source in ("gbOpen", "gbHumanitarian"):
        url = f"https://www.geoboundaries.org/api/current/{source}/{iso3}/{level}/"
        try:
            response = client.get(url)
            if response.status_code == 404:
                continue
            response.raise_for_status()
            metadata = response.json()
            download_url = (
                metadata.get("gjDownloadURL")
                or metadata.get("simplifiedGeometryGeoJSON")
            )
            if not download_url:
                continue
            geo_response = client.get(download_url)
            geo_response.raise_for_status()
            geojson = geo_response.json()
            if geojson.get("type") != "FeatureCollection" or not geojson.get("features"):
                continue
            cache_file.write_text(
                json.dumps({"metadata": metadata, "geojson": geojson}),
                encoding="utf-8",
            )
            return {"metadata": metadata, "geojson": geojson}, source
        except Exception as exc:
            errors.append(f"{source}: {exc}")
    raise RuntimeError("; ".join(errors)[:500] or "Boundary unavailable")


def _countries():
    values = []
    for country in pycountry.countries:
        iso3 = getattr(country, "alpha_3", None)
        if iso3:
            values.append((iso3, country.name))
    return sorted(values)


def run(args):
    data_dir = Path(args.data_dir or default_global_data_dir()).expanduser()
    output = Path(args.output_dir).expanduser()
    cache = output / "boundary-cache"
    output.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)

    level = args.level.upper()
    if level not in {"ADM0", "ADM1"}:
        raise SystemExit("Initial global runner supports ADM0 and ADM1 only.")

    selected = set(x.strip().upper() for x in args.countries.split(",") if x.strip()) if args.countries else None
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

    result_fields = [
        "country_iso3", "country_name", "admin_level", "admin_name",
        "admin_id", "boundary_source", "boundary_year",
        "dataset_id", "source_year", "technology", "crop_code", "crop_name",
        "crop_band", "physical_area_ha", "harvested_area_ha", "production_t",
        "yield_t_ha_area_weighted", "valid_cells",
        "yield_crosscheck_abs_kg_ha", "spatial_status", "computed_at_utc",
    ]
    error_fields = ["country_iso3", "country_name", "admin_level", "error", "failed_at_utc"]
    write_header = not summary_path.exists() or not args.resume
    if write_header:
        summary_path.write_text("", encoding="utf-8")
    if not errors_path.exists() or not args.resume:
        errors_path.write_text("", encoding="utf-8")

    with (
        summary_path.open("a", newline="", encoding="utf-8-sig") as result_file,
        errors_path.open("a", newline="", encoding="utf-8-sig") as error_file,
        httpx.Client(timeout=180, follow_redirects=True) as client,
    ):
        writer = csv.DictWriter(result_file, fieldnames=result_fields)
        error_writer = csv.DictWriter(error_file, fieldnames=error_fields)
        if write_header:
            writer.writeheader()
        if errors_path.stat().st_size == 0:
            error_writer.writeheader()

        for index, (iso3, country_name) in enumerate(countries, 1):
            if iso3 in completed:
                print(f"[{index}/{len(countries)}] SKIP {iso3} (already complete)", flush=True)
                continue
            print(f"[{index}/{len(countries)}] {iso3} {country_name}", flush=True)
            try:
                boundary, boundary_source = _load_boundary(
                    client, iso3, level, cache
                )
                features = boundary["geojson"]["features"]
                if level == "ADM0":
                    geometry = unary_union([
                        shape(feature["geometry"]) for feature in features
                        if feature.get("geometry")
                    ])
                    zones = [{
                        "name": country_name,
                        "id": iso3,
                        "geometry": geometry.__geo_interface__,
                    }]
                else:
                    zones = []
                    for feature in features:
                        props = feature.get("properties") or {}
                        name = (
                            props.get("shapeName")
                            or props.get("name")
                            or props.get("NAME_1")
                            or props.get("name_1")
                            or "Unknown"
                        )
                        zone_id = (
                            props.get("shapeID")
                            or props.get("shapeISO")
                            or props.get("shapeID")
                            or f"{iso3}-{len(zones)+1}"
                        )
                        zones.append({
                            "name": str(name),
                            "id": str(zone_id),
                            "geometry": feature["geometry"],
                        })

                metadata = boundary.get("metadata") or {}
                for zone in zones:
                    summaries = aggregate_mapspam_zone_all_crops(
                        zone["geometry"], data_dir, technology=args.technology
                    )
                    for item in summaries:
                        band = item["crop_band"]
                        crop_code, crop_name = MAPSPAM_CROPS[band - 1]
                        has_data = item["valid_cells"] > 0
                        writer.writerow({
                            "country_iso3": iso3,
                            "country_name": country_name,
                            "admin_level": level,
                            "admin_name": zone["name"],
                            "admin_id": zone["id"],
                            "boundary_source": boundary_source,
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
                            "spatial_status": "ESTIMATED" if has_data else "NO_RASTER_CELLS",
                            "computed_at_utc": datetime.now(timezone.utc).isoformat(),
                        })
                    result_file.flush()
                if level == "ADM0":
                    completed.add(iso3)
                    completed_path.write_text(
                        json.dumps(sorted(completed), indent=2),
                        encoding="utf-8",
                    )
                print(f"  PASS: {len(zones)} zone(s) x {len(MAPSPAM_CROPS)} crops", flush=True)
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
                time.sleep(0.5)

    print(json.dumps({
        "level": level,
        "countries_requested": len(countries),
        "countries_completed": len(completed),
        "results_csv": str(summary_path),
        "errors_csv": str(errors_path),
        "completed_checkpoint": str(completed_path),
        "source": "MAPSPAM 2020 v2r2",
        "crop_count": len(MAPSPAM_CROPS),
        "interpretation": "2020 gridded estimates, not current-year observations",
    }, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description="Resumable global MAPSPAM country/admin batch")
    parser.add_argument("--level", default="ADM0", help="ADM0 or ADM1")
    parser.add_argument("--countries", default="", help="Optional comma-separated ISO3 list")
    parser.add_argument("--technology", choices=["all", "irrigated", "rainfed"], default="all")
    parser.add_argument("--data-dir", default=str(default_global_data_dir()))
    parser.add_argument("--output-dir", default="data/global-results")
    parser.add_argument("--resume", action="store_true", help="Skip completed ADM0 countries")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
