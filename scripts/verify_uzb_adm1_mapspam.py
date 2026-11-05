"""Verify a complete real-data UZB ADM1 MAPSPAM integration run.

Run after downloading the four core MAPSPAM COGs:
  python scripts/verify_uzb_adm1_mapspam.py RESULTS.csv ERRORS.csv
"""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

from backend.app.services.global_raster_catalog import MAPSPAM_CROPS


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise SystemExit(f"FAIL: CSV file not found: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def finite_nonnegative(row: dict[str, str], field: str, identity: str) -> float:
    value = row.get(field, "")
    if value == "":
        raise SystemExit(f"FAIL: {identity} has an empty {field}")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"FAIL: {identity} has invalid {field}: {value!r}") from exc
    if not math.isfinite(parsed) or parsed < 0:
        raise SystemExit(f"FAIL: {identity} has out-of-range {field}: {value!r}")
    return parsed


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: verify_uzb_adm1_mapspam.py RESULTS.csv ERRORS.csv"
        )

    result_path = Path(sys.argv[1])
    error_path = Path(sys.argv[2])
    rows = read_csv(result_path)
    errors = read_csv(error_path)

    if errors:
        raise SystemExit(
            "FAIL: MAPSPAM ADM1 runner recorded errors: "
            + json.dumps(errors[:5], ensure_ascii=False)
        )

    expected_crops = {code for code, _ in MAPSPAM_CROPS}
    if len(expected_crops) != 46:
        raise SystemExit(f"FAIL: expected 46 catalog crops, got {len(expected_crops)}")

    if not rows:
        raise SystemExit("FAIL: MAPSPAM ADM1 result is empty")

    zone_names: dict[str, str] = {}
    crops_by_zone: dict[str, set[str]] = defaultdict(set)
    identities: set[tuple[str, str, str, str]] = set()
    status_counts: Counter[str] = Counter()

    for index, row in enumerate(rows, 1):
        identity_label = f"CSV row {index}"
        if row.get("country_iso3") != "UZB":
            raise SystemExit(f"FAIL: {identity_label} is not UZB")
        if row.get("admin_level") != "ADM1":
            raise SystemExit(f"FAIL: {identity_label} is not ADM1")
        if row.get("dataset_id") != "mapspam-2020-v2r2":
            raise SystemExit(f"FAIL: {identity_label} has wrong dataset_id")
        if row.get("source_year") != "2020":
            raise SystemExit(f"FAIL: {identity_label} has wrong source year")
        if row.get("technology") != "all":
            raise SystemExit(f"FAIL: {identity_label} has wrong technology")

        zone_id = row.get("admin_id", "")
        zone_name = row.get("admin_name", "")
        crop_code = row.get("crop_code", "")
        if not zone_id or not zone_name:
            raise SystemExit(f"FAIL: {identity_label} has empty admin identity")
        if crop_code not in expected_crops:
            raise SystemExit(f"FAIL: {identity_label} has unknown crop_code {crop_code!r}")

        previous_name = zone_names.setdefault(zone_id, zone_name)
        if previous_name != zone_name:
            raise SystemExit(f"FAIL: zone {zone_id} has inconsistent names")

        crop_band = int(row.get("crop_band", "0"))
        expected_band = next(
            (band for band, (code, _) in enumerate(MAPSPAM_CROPS, 1) if code == crop_code),
            None,
        )
        if crop_band != expected_band:
            raise SystemExit(
                f"FAIL: {identity_label} crop band {crop_band} != expected {expected_band}"
            )

        key = ("UZB", zone_id, row["technology"], crop_code)
        if key in identities:
            raise SystemExit(f"FAIL: duplicate result identity {key!r}")
        identities.add(key)
        crops_by_zone[zone_id].add(crop_code)

        for field in (
            "physical_area_ha",
            "harvested_area_ha",
            "production_t",
        ):
            finite_nonnegative(row, field, identity_label)

        valid_cells = finite_nonnegative(row, "valid_cells", identity_label)
        if not valid_cells.is_integer():
            raise SystemExit(f"FAIL: {identity_label} valid_cells must be an integer")

        weighted_yield = row.get("yield_t_ha_area_weighted", "")
        if weighted_yield:
            finite_nonnegative(row, "yield_t_ha_area_weighted", identity_label)

        crosscheck = row.get("yield_crosscheck_abs_kg_ha", "")
        if crosscheck:
            finite_nonnegative(row, "yield_crosscheck_abs_kg_ha", identity_label)

        spatial_status = row.get("spatial_status", "")
        if spatial_status not in {"ESTIMATED", "NO_RASTER_CELLS"}:
            raise SystemExit(
                f"FAIL: {identity_label} has unknown spatial_status {spatial_status!r}"
            )
        if spatial_status == "ESTIMATED" and valid_cells <= 0:
            raise SystemExit(f"FAIL: {identity_label} estimated without raster cells")
        if spatial_status == "NO_RASTER_CELLS" and valid_cells != 0:
            raise SystemExit(f"FAIL: {identity_label} has cells but says NO_RASTER_CELLS")
        status_counts[spatial_status] += 1

    if len(zone_names) != 14:
        raise SystemExit(
            f"FAIL: expected 14 UZB ADM1 zones, found {len(zone_names)}"
        )

    incomplete = {
        zone_id: sorted(expected_crops - crop_codes)
        for zone_id, crop_codes in crops_by_zone.items()
        if crop_codes != expected_crops
    }
    if incomplete:
        raise SystemExit(
            "FAIL: zones do not contain all 46 crops: "
            + json.dumps(incomplete, ensure_ascii=False)
        )

    expected_rows = 14 * len(expected_crops)
    if len(rows) != expected_rows or len(identities) != expected_rows:
        raise SystemExit(
            f"FAIL: expected {expected_rows} unique rows, "
            f"got {len(rows)} rows / {len(identities)} unique identities"
        )

    report = {
        "status": "PASS",
        "country_iso3": "UZB",
        "admin_level": "ADM1",
        "dataset_id": "mapspam-2020-v2r2",
        "source_year": 2020,
        "zones": len(zone_names),
        "crops_per_zone": len(expected_crops),
        "result_rows": len(rows),
        "unique_result_identities": len(identities),
        "spatial_status_counts": dict(status_counts),
        "admin_names": sorted(zone_names.values()),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
