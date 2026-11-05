"""Compare Uzbekistan ADM1 totals with the official MAPSPAM ADM0 zonal result.

This is a conservation-style QA check. The 14 regional polygons should reproduce
country totals to within a small tolerance; source values remain modeled 2020
MAPSPAM grid estimates rather than administrative statistical observations.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.global_raster_catalog import MAPSPAM_CROPS

AREA_FIELDS = ("physical_area_ha", "harvested_area_ha")
SUM_FIELDS = (*AREA_FIELDS, "production_t")
MAX_RELATIVE_SUM_DIFFERENCE = 0.01  # 1%; boundaries can differ slightly at coast/edges.
MAX_YIELD_DIFFERENCE_T_HA = 0.05


def load_rows(path: Path, level: str) -> dict[str, dict]:
    if not path.is_file():
        raise SystemExit(f"FAIL: CSV file not found: {path}")

    rows_by_crop: dict[str, dict] = {}
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            if row.get("country_iso3") != "UZB" or row.get("admin_level") != level:
                raise SystemExit(f"FAIL: unexpected country/level in {path.name}")
            if row.get("dataset_id") != "mapspam-2020-v2r2" or row.get("source_year") != "2020":
                raise SystemExit(f"FAIL: wrong dataset/year in {path.name}")
            if row.get("technology") != "all":
                raise SystemExit(f"FAIL: wrong MAPSPAM technology in {path.name}")

            crop = row.get("crop_code", "")
            if crop not in {code for code, _ in MAPSPAM_CROPS}:
                raise SystemExit(f"FAIL: unknown crop code {crop!r} in {path.name}")
            if crop in rows_by_crop:
                raise SystemExit(f"FAIL: duplicate {level} crop row {crop!r} in {path.name}")
            rows_by_crop[crop] = row

    expected = {code for code, _ in MAPSPAM_CROPS}
    if set(rows_by_crop) != expected:
        missing = sorted(expected - set(rows_by_crop))
        extra = sorted(set(rows_by_crop) - expected)
        raise SystemExit(
            f"FAIL: {level} CSV must contain 46 crop rows; "
            f"missing={missing}, extra={extra}"
        )
    return rows_by_crop


def numeric(row: dict, key: str) -> float | None:
    raw = row.get(key, "")
    if raw == "":
        return None
    value = float(raw)
    if not math.isfinite(value) or value < 0:
        raise SystemExit(f"FAIL: invalid {key} value {raw!r}")
    return value


def relative_difference(a: float, b: float) -> float:
    scale = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / scale


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(
            "Usage: verify_uzb_adm1_vs_adm0.py ADM1.csv ADM0.csv"
        )

    adm1 = load_rows(Path(sys.argv[1]), "ADM1")
    adm0 = load_rows(Path(sys.argv[2]), "ADM0")

    metrics = []
    failures = []
    max_area_relative = 0.0
    max_production_relative = 0.0
    max_yield_abs = 0.0

    for crop, _name in MAPSPAM_CROPS:
        regional_rows = [row for row in []]  # replaced below from the single-crop index
        # ADM1 file is re-read by crop from the raw 14-row table below.
        # This branch is intentionally populated by the separate grouped reader.
        pass


def load_adm1_grouped(path: Path) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        for row in csv.DictReader(stream):
            grouped[row.get("crop_code", "")].append(row)
    return grouped


def compare(adm1_path: Path, adm0_path: Path) -> dict:
    adm0 = load_rows(adm0_path, "ADM0")
    adm1_grouped = load_adm1_grouped(adm1_path)
    expected = {code for code, _ in MAPSPAM_CROPS}
    if set(adm1_grouped) != expected:
        raise SystemExit("FAIL: ADM1 result does not cover all 46 crop codes")

    metrics = []
    failures = []
    max_area_relative = 0.0
    max_production_relative = 0.0
    max_yield_abs = 0.0

    for crop, crop_name in MAPSPAM_CROPS:
        rows = adm1_grouped[crop]
        if len(rows) != 14:
            raise SystemExit(f"FAIL: {crop} has {len(rows)} ADM1 rows, expected 14")
        admin_ids = {row.get("admin_id") for row in rows}
        if len(admin_ids) != 14:
            raise SystemExit(f"FAIL: {crop} contains duplicate ADM1 region IDs")

        country = adm0[crop]
        record = {
            "crop_code": crop,
            "crop_name": crop_name,
            "adm1_regions": len(rows),
        }

        for field in SUM_FIELDS:
            regional_total = sum(numeric(row, field) or 0.0 for row in rows)
            national_total = numeric(country, field) or 0.0
            rel = relative_difference(regional_total, national_total)
            record[f"{field}_adm1_sum"] = regional_total
            record[f"{field}_adm0"] = national_total
            record[f"{field}_relative_difference"] = rel

            if field == "physical_area_ha":
                max_area_relative = max(max_area_relative, rel)
            elif field == "production_t":
                max_production_relative = max(max_production_relative, rel)

            if rel > MAX_RELATIVE_SUM_DIFFERENCE:
                failures.append({
                    "crop_code": crop,
                    "metric": field,
                    "adm1_sum": regional_total,
                    "adm0": national_total,
                    "relative_difference": rel,
                })

        regional_harvested = sum(numeric(row, "harvested_area_ha") or 0.0 for row in rows)
        regional_weighted_yield_num = sum(
            (numeric(row, "yield_t_ha_area_weighted") or 0.0)
            * (numeric(row, "harvested_area_ha") or 0.0)
            for row in rows
        )
        regional_yield = (
            regional_weighted_yield_num / regional_harvested
            if regional_harvested > 0 else None
        )
        national_yield = numeric(country, "yield_t_ha_area_weighted")
        if regional_yield is None and national_yield is None:
            yield_difference = 0.0
        elif regional_yield is None or national_yield is None:
            yield_difference = float("inf")
        else:
            yield_difference = abs(regional_yield - national_yield)

        record["yield_t_ha_area_weighted_adm1"] = regional_yield
        record["yield_t_ha_area_weighted_adm0"] = national_yield
        record["yield_absolute_difference_t_ha"] = yield_difference
        if math.isfinite(yield_difference):
            max_yield_abs = max(max_yield_abs, yield_difference)
        if yield_difference > MAX_YIELD_DIFFERENCE_T_HA:
            failures.append({
                "crop_code": crop,
                "metric": "yield_t_ha_area_weighted",
                "adm1": regional_yield,
                "adm0": national_yield,
                "absolute_difference_t_ha": yield_difference,
            })
        metrics.append(record)

    report = {
        "status": "PASS" if not failures else "FAIL",
        "country_iso3": "UZB",
        "dataset_id": "mapspam-2020-v2r2",
        "source_year": 2020,
        "adm1_regions": 14,
        "crops": 46,
        "comparisons": len(metrics),
        "tolerances": {
            "area_and_production_relative_difference_max": MAX_RELATIVE_SUM_DIFFERENCE,
            "yield_absolute_difference_t_ha_max": MAX_YIELD_DIFFERENCE_T_HA,
        },
        "observed_maxima": {
            "physical_area_relative_difference": max_area_relative,
            "production_relative_difference": max_production_relative,
            "yield_absolute_difference_t_ha": max_yield_abs,
        },
        "failures": failures,
        "per_crop": metrics,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    if len(sys.argv) == 3:
        compare(Path(sys.argv[1]), Path(sys.argv[2]))
    else:
        main()
