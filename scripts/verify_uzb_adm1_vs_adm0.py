"""Compare Uzbekistan ADM1 totals with the official MAPSPAM ADM0 zonal result."""
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

SUM_FIELDS = ("physical_area_ha", "harvested_area_ha", "production_t")
MAX_RELATIVE_SUM_DIFFERENCE = 0.01
MAX_YIELD_DIFFERENCE_T_HA = 0.05


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise SystemExit(f"FAIL: CSV file not found: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as stream:
        return list(csv.DictReader(stream))


def validate_row(row: dict[str, str], level: str, path: Path) -> None:
    if row.get("country_iso3") != "UZB" or row.get("admin_level") != level:
        raise SystemExit(f"FAIL: unexpected country/admin level in {path.name}")
    if row.get("dataset_id") != "mapspam-2020-v2r2" or row.get("source_year") != "2020":
        raise SystemExit(f"FAIL: wrong dataset/year in {path.name}")
    if row.get("technology") != "all":
        raise SystemExit(f"FAIL: wrong MAPSPAM technology in {path.name}")
    if row.get("crop_code") not in {code for code, _ in MAPSPAM_CROPS}:
        raise SystemExit(f"FAIL: unknown crop code {row.get('crop_code')!r}")


def number(row: dict[str, str], field: str) -> float | None:
    raw = row.get(field, "")
    if raw == "":
        return None
    value = float(raw)
    if not math.isfinite(value) or value < 0:
        raise SystemExit(f"FAIL: invalid {field} value {raw!r}")
    return value


def relative_difference(a: float, b: float) -> float:
    return abs(a - b) / max(abs(a), abs(b), 1e-9)


def compare(adm1_path: Path, adm0_path: Path) -> dict:
    adm1_rows = read_csv(adm1_path)
    adm0_rows = read_csv(adm0_path)
    if len(adm1_rows) != 14 * len(MAPSPAM_CROPS):
        raise SystemExit(f"FAIL: expected 644 ADM1 rows, got {len(adm1_rows)}")
    if len(adm0_rows) != len(MAPSPAM_CROPS):
        raise SystemExit(f"FAIL: expected 46 ADM0 rows, got {len(adm0_rows)}")

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    national: dict[str, dict[str, str]] = {}
    for row in adm1_rows:
        validate_row(row, "ADM1", adm1_path)
        grouped[row["crop_code"]].append(row)
    for row in adm0_rows:
        validate_row(row, "ADM0", adm0_path)
        crop = row["crop_code"]
        if crop in national:
            raise SystemExit(f"FAIL: duplicate ADM0 crop row {crop}")
        national[crop] = row

    expected = {code for code, _ in MAPSPAM_CROPS}
    if set(grouped) != expected or set(national) != expected:
        raise SystemExit("FAIL: ADM0/ADM1 files do not cover the same 46 MAPSPAM crops")

    metrics = []
    failures = []
    max_relative = {field: 0.0 for field in SUM_FIELDS}
    max_yield_difference = 0.0

    for crop, crop_name in MAPSPAM_CROPS:
        rows = grouped[crop]
        if len(rows) != 14:
            raise SystemExit(f"FAIL: {crop} has {len(rows)} ADM1 rows, expected 14")
        admin_ids = {row.get("admin_id") for row in rows}
        if len(admin_ids) != 14 or None in admin_ids or "" in admin_ids:
            raise SystemExit(f"FAIL: {crop} has duplicate/empty ADM1 IDs")
        country = national[crop]

        item = {"crop_code": crop, "crop_name": crop_name, "adm1_regions": len(rows)}
        for field in SUM_FIELDS:
            regional = sum(number(row, field) or 0.0 for row in rows)
            country_total = number(country, field) or 0.0
            difference = relative_difference(regional, country_total)
            item[f"{field}_adm1_sum"] = regional
            item[f"{field}_adm0"] = country_total
            item[f"{field}_relative_difference"] = difference
            max_relative[field] = max(max_relative[field], difference)
            if difference > MAX_RELATIVE_SUM_DIFFERENCE:
                failures.append({
                    "crop_code": crop,
                    "metric": field,
                    "adm1_sum": regional,
                    "adm0": country_total,
                    "relative_difference": difference,
                })

        region_area = sum(number(row, "harvested_area_ha") or 0.0 for row in rows)
        weighted_yield_sum = sum(
            (number(row, "yield_t_ha_area_weighted") or 0.0)
            * (number(row, "harvested_area_ha") or 0.0)
            for row in rows
        )
        region_yield = weighted_yield_sum / region_area if region_area > 0 else None
        country_yield = number(country, "yield_t_ha_area_weighted")
        if region_yield is None and country_yield is None:
            yield_difference = 0.0
        elif region_yield is None or country_yield is None:
            yield_difference = float("inf")
        else:
            yield_difference = abs(region_yield - country_yield)

        item["yield_t_ha_area_weighted_adm1"] = region_yield
        item["yield_t_ha_area_weighted_adm0"] = country_yield
        item["yield_absolute_difference_t_ha"] = yield_difference
        if math.isfinite(yield_difference):
            max_yield_difference = max(max_yield_difference, yield_difference)
        if yield_difference > MAX_YIELD_DIFFERENCE_T_HA:
            failures.append({
                "crop_code": crop,
                "metric": "yield_t_ha_area_weighted",
                "adm1": region_yield,
                "adm0": country_yield,
                "absolute_difference_t_ha": yield_difference,
            })
        metrics.append(item)

    return {
        "status": "PASS" if not failures else "FAIL",
        "country_iso3": "UZB",
        "dataset_id": "mapspam-2020-v2r2",
        "source_year": 2020,
        "adm1_regions": 14,
        "crops": len(MAPSPAM_CROPS),
        "comparisons": len(metrics),
        "tolerances": {
            "area_and_production_relative_difference_max": MAX_RELATIVE_SUM_DIFFERENCE,
            "yield_absolute_difference_t_ha_max": MAX_YIELD_DIFFERENCE_T_HA,
        },
        "observed_maxima": {
            f"{field}_relative_difference": value
            for field, value in max_relative.items()
        } | {
            "yield_absolute_difference_t_ha": max_yield_difference,
        },
        "failures": failures,
        "per_crop": metrics,
    }


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: verify_uzb_adm1_vs_adm0.py ADM1.csv ADM0.csv")
    report = compare(Path(sys.argv[1]), Path(sys.argv[2]))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
