"""Verify public country-level MAPSPAM packages before committing them."""
from __future__ import annotations

import argparse
import gzip
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "docs" / "data" / "mapspam" / "global"
EXPECTED_LICENSE = "CC BY-SA 4.0"
EXPECTED_DATASET = "mapspam-2020-v2r2"
EXPECTED_YEAR = 2020
ALLOWED_LEVELS = {"ADM0", "ADM1", "ADM2"}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("FAIL: " + message)


def finite_nonnegative(value, label: str, *, nullable: bool = False):
    if value is None and nullable:
        return None
    require(isinstance(value, (int, float)) and math.isfinite(float(value)) and value >= 0,
            f"{label} must be a finite non-negative number")
    return float(value)


def verify_package(path: Path, iso: str, metadata: dict) -> tuple[int, int]:
    require(path.is_file(), f"{iso}: package file not found: {path}")
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        payload = json.load(stream)

    require(payload.get("country_iso3") == iso, f"{iso}: country ISO mismatch")
    require(payload.get("dataset_id") == EXPECTED_DATASET, f"{iso}: dataset mismatch")
    require(payload.get("source_year") == EXPECTED_YEAR, f"{iso}: source year mismatch")
    require(payload.get("license") == EXPECTED_LICENSE, f"{iso}: MAPSPAM licence mismatch")
    require(payload.get("source_url") == "https://doi.org/10.7910/DVN/SWPENT",
            f"{iso}: source URL missing or unexpected")

    levels = payload.get("levels")
    require(isinstance(levels, dict) and levels, f"{iso}: no administrative levels")
    require(set(levels).issubset(ALLOWED_LEVELS), f"{iso}: unexpected administrative level")

    total_rows = 0
    total_areas = 0
    for level, level_data in levels.items():
        areas = level_data.get("areas")
        require(isinstance(areas, dict) and areas, f"{iso}/{level}: area dictionary is empty")
        require(int(level_data.get("area_count", -1)) == len(areas),
                f"{iso}/{level}: area_count mismatch")
        require(int(level_data.get("crop_count", -1)) == 46,
                f"{iso}/{level}: expected 46 crop layers")
        total_areas += len(areas)
        total_rows += sum(len((area.get("crops") or {})) for area in areas.values())

        for area_id, area in areas.items():
            require(str(area_id).strip() and str(area.get("name") or "").strip(),
                    f"{iso}/{level}: missing area ID/name")
            crops = area.get("crops") or {}
            require(len(crops) == 46, f"{iso}/{level}/{area_id}: expected 46 crops, got {len(crops)}")
            for crop_code, row in crops.items():
                identity = f"{iso}/{level}/{area_id}/{crop_code}"
                require(isinstance(row, dict), f"{identity}: crop row is not an object")
                cells = finite_nonnegative(row.get("valid_cells"), identity + "/valid_cells")
                require(float(cells).is_integer(), f"{identity}: valid_cells is not an integer")
                yld = finite_nonnegative(row.get("yield_t_ha"), identity + "/yield_t_ha", nullable=True)
                status = row.get("spatial_status")
                if status == "ESTIMATED":
                    require(cells > 0 and yld is not None, f"{identity}: invalid ESTIMATED record")
                elif status == "NO_RASTER_CELLS":
                    require(cells == 0 and yld is None, f"{identity}: missing yield must remain NULL")
                else:
                    require(False, f"{identity}: unsupported spatial_status {status!r}")
                for field in ("physical_area_ha", "harvested_area_ha", "production_t"):
                    finite_nonnegative(row.get(field), identity + "/" + field)

    require(int(metadata.get("row_count", -1)) == total_rows,
            f"{iso}: manifest row_count mismatch")
    require(total_rows > 0, f"{iso}: no summary rows")
    return total_areas, total_rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()

    manifest_path = args.data_dir / "manifest.json"
    require(manifest_path.is_file(), f"manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest.get("dataset_id") == EXPECTED_DATASET, "manifest dataset mismatch")
    require(manifest.get("source_year") == EXPECTED_YEAR, "manifest source year mismatch")
    require(manifest.get("license") == EXPECTED_LICENSE, "manifest licence mismatch")
    countries = manifest.get("countries")
    require(isinstance(countries, dict) and countries, "manifest has no countries")

    total_rows = 0
    total_areas = 0
    for iso, metadata in sorted(countries.items()):
        require(len(iso) == 3 and iso.isalpha() and iso == iso.upper(),
                f"invalid ISO3 country key: {iso!r}")
        filename = str(metadata.get("file") or "")
        require(filename == f"{iso}.json.gz", f"{iso}: unexpected package filename")
        areas, rows = verify_package(args.data_dir / filename, iso, metadata)
        total_areas += areas
        total_rows += rows
        print(f"PASS {iso}: {areas:,} administrative areas / {rows:,} crop summaries")

    require(int(manifest.get("country_count", -1)) == len(countries),
            "manifest country_count mismatch")
    require(int(manifest.get("total_summary_rows", -1)) == total_rows,
            "manifest total_summary_rows mismatch")
    print(json.dumps({
        "status": "PASS",
        "countries": len(countries),
        "admin_areas_across_levels": total_areas,
        "summary_rows": total_rows,
        "compressed_mb": round(sum((args.data_dir / str(row["file"])).stat().st_size
                                   for row in countries.values()) / (1024 * 1024), 2),
        "license": EXPECTED_LICENSE,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
