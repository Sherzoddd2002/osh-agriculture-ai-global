"""Validate and import adjacent MAPSPAM administrative hierarchy levels.

Run this importer once per adjacent pair:
  ADM0 -> ADM1, ADM1 -> ADM2, ADM2 -> ADM3, ADM3 -> ADM4.
Only country groups whose child polygons conserve every parent zone across all
46 crops are eligible for import. --allow-partial-countries keeps valid
countries while reporting rejected countries.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from typing import Any

from .db import SessionLocal, init_db
from .import_mapspam_results import (
    EXPECTED_CROPS,
    MAX_RELATIVE_SUM_DIFFERENCE,
    MAX_YIELD_DIFFERENCE_T_HA,
    SUM_FIELDS,
    _read_level,
    upsert_summary_rows,
)


def _relative_difference(left: float, right: float) -> float:
    return abs(left - right) / max(abs(left), abs(right), 1e-9)


def validate_adjacent_levels(
    parent_rows: list[dict[str, Any]],
    child_rows: list[dict[str, Any]],
    parent_level: str,
    child_level: str,
    *,
    allow_partial_countries: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parent_level = parent_level.upper()
    child_level = child_level.upper()
    if parent_level not in {"ADM0", "ADM1", "ADM2", "ADM3"}:
        raise ValueError("parent_level must be ADM0, ADM1, ADM2 or ADM3")
    if child_level != f"ADM{int(parent_level[-1]) + 1}":
        raise ValueError("parent_level and child_level must be adjacent")

    def scope(row: dict[str, Any]) -> tuple[str, str, int, str]:
        return (
            str(row["country_iso3"]),
            str(row["dataset_id"]),
            int(row["source_year"]),
            str(row["technology"]),
        )

    parents_by_scope: dict[tuple[str, str, int, str], list[dict[str, Any]]] = defaultdict(list)
    children_by_scope: dict[tuple[str, str, int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in parent_rows:
        parents_by_scope[scope(row)].append(row)
    for row in child_rows:
        children_by_scope[scope(row)].append(row)

    scopes = sorted(
        set(parents_by_scope) | set(children_by_scope),
        key=lambda item: (item[0], item[1], item[2], item[3]),
    )
    if not scopes:
        raise ValueError("No MAPSPAM country scopes found")

    accepted: list[dict[str, Any]] = []
    accepted_reports: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for country, dataset_id, source_year, technology in scopes:
        key = (country, dataset_id, source_year, technology)
        label = {
            "country_iso3": country,
            "dataset_id": dataset_id,
            "source_year": source_year,
            "technology": technology,
        }
        parents = parents_by_scope.get(key, [])
        children = children_by_scope.get(key, [])
        try:
            if not parents or not children:
                missing = []
                if not parents:
                    missing.append(parent_level)
                if not children:
                    missing.append(child_level)
                raise ValueError(f"Missing {' and '.join(missing)} rows")

            expected = EXPECTED_CROPS
            parent_zones: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
            child_zones: dict[str, set[str]] = defaultdict(set)
            child_rows_by_parent_crop: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)

            for row in parents:
                if row["admin_level"] != parent_level:
                    raise ValueError("Parent CSV contains the wrong admin level")
                parent_id = str(row["admin_id"])
                crop = str(row["crop_code"])
                if crop in parent_zones[parent_id]:
                    raise ValueError(f"Duplicate parent crop row: {parent_id}/{crop}")
                parent_zones[parent_id][crop] = row

            for parent_id, crops in parent_zones.items():
                if set(crops) != expected:
                    raise ValueError(
                        f"Parent zone {parent_id} does not contain all 46 crops"
                    )

            parent_ids = set(parent_zones)
            for row in children:
                if row["admin_level"] != child_level:
                    raise ValueError("Child CSV contains the wrong admin level")
                if row.get("parent_admin_level") != parent_level:
                    raise ValueError(
                        f"{child_level} row {row['admin_id']} has incorrect parent level"
                    )
                parent_id = row.get("parent_admin_id")
                if not parent_id or parent_id not in parent_ids:
                    raise ValueError(
                        f"{child_level} row {row['admin_id']} references missing "
                        f"{parent_level} parent {parent_id!r}"
                    )
                zone_id = str(row["admin_id"])
                crop = str(row["crop_code"])
                child_zones[zone_id].add(crop)
                child_rows_by_parent_crop[(parent_id, crop)].append(row)

            incomplete_children = [
                zone_id for zone_id, crops in child_zones.items()
                if crops != expected
            ]
            if incomplete_children:
                raise ValueError(
                    f"Child zones missing crop rows: {incomplete_children[:10]}"
                )

            if not child_zones:
                raise ValueError("No child administrative zones found")

            max_relative = {field: 0.0 for field in SUM_FIELDS}
            max_yield_difference = 0.0
            for parent_id, parent_crop_rows in parent_zones.items():
                if not any(
                    (parent_id, crop) in child_rows_by_parent_crop
                    for crop in expected
                ):
                    raise ValueError(f"Parent zone {parent_id} has no child zones")

                for crop in sorted(expected):
                    regional = child_rows_by_parent_crop.get((parent_id, crop), [])
                    if not regional:
                        raise ValueError(
                            f"Parent zone {parent_id} has no child rows for crop {crop}"
                        )
                    parent = parent_crop_rows[crop]
                    for field in SUM_FIELDS:
                        regional_total = sum(float(row[field]) for row in regional)
                        parent_total = float(parent[field])
                        difference = _relative_difference(regional_total, parent_total)
                        max_relative[field] = max(max_relative[field], difference)
                        if difference > MAX_RELATIVE_SUM_DIFFERENCE:
                            raise ValueError(
                                f"{parent_id}/{crop} {field} child/parent difference "
                                f"{difference:.6%} exceeds 1%"
                            )

                    child_area = sum(float(row["harvested_area_ha"]) for row in regional)
                    child_yield_numerator = sum(
                        float(row["yield_t_ha_area_weighted"] or 0.0)
                        * float(row["harvested_area_ha"])
                        for row in regional
                    )
                    child_yield = (
                        child_yield_numerator / child_area if child_area > 0 else None
                    )
                    parent_yield = parent["yield_t_ha_area_weighted"]
                    if child_yield is None and parent_yield is None:
                        yield_difference = 0.0
                    elif child_yield is None or parent_yield is None:
                        yield_difference = float("inf")
                    else:
                        yield_difference = abs(child_yield - float(parent_yield))
                    if yield_difference > MAX_YIELD_DIFFERENCE_T_HA:
                        raise ValueError(
                            f"{parent_id}/{crop} weighted yield difference "
                            f"{yield_difference:.6f} t/ha exceeds 0.05 t/ha"
                        )
                    if yield_difference < float("inf"):
                        max_yield_difference = max(
                            max_yield_difference, yield_difference
                        )

            parent_names = {str(row["country_name"]) for row in parents}
            child_names = {str(row["country_name"]) for row in children}
            if len(parent_names) != 1 or parent_names != child_names:
                raise ValueError("Parent/child country names do not match")

            accepted.extend(parents)
            accepted.extend(children)
            accepted_reports.append({
                **label,
                "parent_level": parent_level,
                "child_level": child_level,
                "parent_zone_count": len(parent_zones),
                "child_zone_count": len(child_zones),
                "parent_rows": len(parents),
                "child_rows": len(children),
                "crop_count": len(expected),
                "max_relative_differences": max_relative,
                "max_weighted_yield_difference_t_ha": max_yield_difference,
                "status": "PASS",
            })
        except Exception as exc:
            rejected.append({**label, "reason": str(exc)[:1000]})

    if rejected and not allow_partial_countries:
        raise ValueError(
            f"Hierarchy validation rejected {len(rejected)} country scope(s): "
            + json.dumps(rejected[:10], ensure_ascii=False)
        )
    if not accepted:
        raise ValueError("No country passed adjacent-level MAPSPAM validation")

    report = {
        "status": "PARTIAL" if rejected else "PASS",
        "parent_level": parent_level,
        "child_level": child_level,
        "countries_total": len(scopes),
        "countries_passed": sorted({row["country_iso3"] for row in accepted_reports}),
        "countries_rejected": sorted({row["country_iso3"] for row in rejected}),
        "country_scopes_passed": len(accepted_reports),
        "country_scopes_rejected": len(rejected),
        "parent_rows": sum(row["parent_rows"] for row in accepted_reports),
        "child_rows": sum(row["child_rows"] for row in accepted_reports),
        "accepted_rows": len(accepted),
        "crop_count": len(EXPECTED_CROPS),
        "max_relative_differences": {
            field: max(
                (row["max_relative_differences"][field] for row in accepted_reports),
                default=0.0,
            )
            for field in SUM_FIELDS
        },
        "max_weighted_yield_difference_t_ha": max(
            (row["max_weighted_yield_difference_t_ha"] for row in accepted_reports),
            default=0.0,
        ),
        "rejected_groups": rejected,
    }
    return accepted, report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate/import adjacent MAPSPAM ADM0-ADM4 hierarchy levels"
    )
    parser.add_argument("--parent-level", required=True, choices=["ADM0", "ADM1", "ADM2", "ADM3"])
    parser.add_argument("--child-level", required=True, choices=["ADM1", "ADM2", "ADM3", "ADM4"])
    parser.add_argument("--parent-csv", required=True)
    parser.add_argument("--child-csv", required=True)
    parser.add_argument("--allow-partial-countries", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    parent_level = args.parent_level.upper()
    child_level = args.child_level.upper()
    expected_child = f"ADM{int(parent_level[-1]) + 1}"
    if child_level != expected_child:
        parser.error("parent-level and child-level must be adjacent")

    parent_rows = _read_level(args.parent_csv, parent_level)
    child_rows = _read_level(args.child_csv, child_level)
    rows, report = validate_adjacent_levels(
        parent_rows,
        child_rows,
        parent_level,
        child_level,
        allow_partial_countries=args.allow_partial_countries,
    )

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
