"""Validate and import adjacent MAPSPAM administrative hierarchy levels.

For matching boundary vintages, parent/child crop totals must conserve.
When boundary vintages differ, the importer can explicitly accept complete
parent links without pretending that cross-vintage areas and production reconcile.
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


def _weighted_yield(rows: list[dict[str, Any]]) -> float | None:
    weighted_sum = 0.0
    weight_sum = 0.0
    for row in rows:
        area = float(row["harvested_area_ha"])
        value = row["yield_t_ha_area_weighted"]
        if value is None or area <= 0:
            continue
        weighted_sum += float(value) * area
        weight_sum += area
    return weighted_sum / weight_sum if weight_sum > 0 else None


def validate_adjacent_levels(
    parent_rows: list[dict[str, Any]],
    child_rows: list[dict[str, Any]],
    parent_level: str,
    child_level: str,
    *,
    allow_partial_countries: bool = False,
    allow_unreconciled_boundaries: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Validate parent links and, when possible, parent-child conservation.

    A differing or unknown administrative boundary vintage is not silently
    treated as a conserved hierarchy. It requires the explicit
    allow_unreconciled_boundaries option and is labelled in every accepted row.
    """
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
    accepted_groups: list[dict[str, Any]] = []
    rejected_groups: list[dict[str, Any]] = []

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
        if not parents or not children:
            missing = []
            if not parents:
                missing.append(parent_level)
            if not children:
                missing.append(child_level)
            rejected_groups.append({
                **label,
                "parent_admin_id": None,
                "reason": f"Missing {' and '.join(missing)} rows",
            })
            continue

        parent_names = {str(row["country_name"]).strip() for row in parents}
        child_names = {str(row["country_name"]).strip() for row in children}
        if len(parent_names) != 1 or parent_names != child_names:
            rejected_groups.append({
                **label,
                "parent_admin_id": None,
                "reason": "Parent/child country names do not match",
            })
            continue

        parent_years = {row.get("boundary_year") for row in parents}
        child_years = {row.get("boundary_year") for row in children}
        if (
            len(parent_years) == 1
            and len(child_years) == 1
            and None not in parent_years
            and None not in child_years
        ):
            parent_year = next(iter(parent_years))
            child_year = next(iter(child_years))
            if parent_year == child_year:
                validation_status = "CONSERVATION_PASS_PENDING"
                check_conservation = True
            else:
                validation_status = "BOUNDARY_VINTAGE_MISMATCH_NOT_RECONCILED"
                check_conservation = False
        else:
            parent_year = sorted(str(x) for x in parent_years)
            child_year = sorted(str(x) for x in child_years)
            validation_status = "BOUNDARY_VINTAGE_UNKNOWN_NOT_RECONCILED"
            check_conservation = False

        if not check_conservation and not allow_unreconciled_boundaries:
            rejected_groups.append({
                **label,
                "parent_admin_id": None,
                "reason": (
                    "Boundary vintages differ or are unknown; pass "
                    "--allow-unreconciled-boundaries to import complete linked "
                    "summaries without claiming conservation"
                ),
                "parent_boundary_years": sorted(str(x) for x in parent_years),
                "child_boundary_years": sorted(str(x) for x in child_years),
            })
            continue

        parent_zones: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for row in parents:
            if row["admin_level"] != parent_level:
                rejected_groups.append({
                    **label,
                    "parent_admin_id": row.get("admin_id"),
                    "reason": "Parent CSV contains the wrong admin level",
                })
                continue
            parent_id = str(row["admin_id"])
            crop = str(row["crop_code"])
            if crop in parent_zones[parent_id]:
                rejected_groups.append({
                    **label,
                    "parent_admin_id": parent_id,
                    "reason": f"Duplicate parent crop row {parent_id}/{crop}",
                })
                continue
            parent_zones[parent_id][crop] = row

        child_zones: dict[str, set[str]] = defaultdict(set)
        child_parent_ids: dict[str, set[str]] = defaultdict(set)
        child_rows_by_parent_crop: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        orphan_rows = 0
        for row in children:
            if row["admin_level"] != child_level:
                orphan_rows += 1
                continue
            if row.get("parent_admin_level") != parent_level:
                orphan_rows += 1
                continue
            parent_id = str(row.get("parent_admin_id") or "")
            if parent_id not in parent_zones:
                orphan_rows += 1
                continue
            if child_level in {"ADM2", "ADM3", "ADM4"}:
                if not row.get("parent_link_method"):
                    orphan_rows += 1
                    continue
                declared_parent_year = row.get("parent_boundary_year")
                if (
                    declared_parent_year is not None
                    and parent_zones[parent_id]
                    and next(iter(parent_zones[parent_id].values())).get("boundary_year")
                    != declared_parent_year
                ):
                    orphan_rows += 1
                    continue
            zone_id = str(row["admin_id"])
            crop = str(row["crop_code"])
            child_zones[zone_id].add(crop)
            child_parent_ids[zone_id].add(parent_id)
            child_rows_by_parent_crop[(parent_id, crop)].append(row)

        if orphan_rows:
            rejected_groups.append({
                **label,
                "parent_admin_id": None,
                "reason": f"{orphan_rows} child rows have invalid or missing parent links",
            })

        incomplete_children = [
            zone_id for zone_id, crops in child_zones.items()
            if crops != EXPECTED_CROPS or len(child_parent_ids[zone_id]) != 1
        ]
        child_scope_invalid = {
            zone_id for zone_id, crops in child_zones.items()
            if crops != EXPECTED_CROPS or len(child_parent_ids[zone_id]) != 1
        }

        country_accepted_before = len(accepted)
        for parent_id, parent_crop_rows in parent_zones.items():
            reason = None
            if set(parent_crop_rows) != EXPECTED_CROPS:
                reason = f"Parent zone {parent_id} does not contain all 46 crops"
            child_ids = [
                zone_id for zone_id, linked in child_parent_ids.items()
                if linked == {parent_id}
            ]
            if reason is None and not child_ids:
                reason = f"Parent zone {parent_id} has no child zones"
            if reason is None:
                invalid_ids = [zone_id for zone_id in child_ids if zone_id in child_scope_invalid]
                if invalid_ids:
                    reason = f"Child zones have incomplete crop/link coverage: {invalid_ids[:10]}"

            parent_zone_children = [
                row for row in children if row.get("parent_admin_id") == parent_id
                and row.get("admin_id") in child_ids
            ]
            if reason is None and check_conservation:
                max_relative = {field: 0.0 for field in SUM_FIELDS}
                max_yield_difference = 0.0
                for crop in sorted(EXPECTED_CROPS):
                    regional = child_rows_by_parent_crop.get((parent_id, crop), [])
                    if not regional:
                        reason = f"{parent_id} has no child rows for crop {crop}"
                        break
                    parent = parent_crop_rows[crop]
                    for field in SUM_FIELDS:
                        regional_total = sum(float(row[field]) for row in regional)
                        parent_total = float(parent[field])
                        difference = _relative_difference(regional_total, parent_total)
                        max_relative[field] = max(max_relative[field], difference)
                        if difference > MAX_RELATIVE_SUM_DIFFERENCE:
                            reason = (
                                f"{parent_id}/{crop} {field} child/parent difference "
                                f"{difference:.6%} exceeds 1%"
                            )
                            break
                    if reason:
                        break

                    child_yield = _weighted_yield(regional)
                    parent_yield = parent["yield_t_ha_area_weighted"]
                    if child_yield is None and parent_yield is None:
                        yield_difference = 0.0
                    elif child_yield is None or parent_yield is None:
                        yield_difference = float("inf")
                    else:
                        yield_difference = abs(child_yield - float(parent_yield))
                    if yield_difference > MAX_YIELD_DIFFERENCE_T_HA:
                        reason = (
                            f"{parent_id}/{crop} weighted yield difference "
                            f"{yield_difference:.6f} t/ha exceeds 0.05 t/ha"
                        )
                        break
                    if yield_difference < float("inf"):
                        max_yield_difference = max(max_yield_difference, yield_difference)
            else:
                max_relative = None
                max_yield_difference = None

            if reason:
                rejected_groups.append({
                    **label,
                    "parent_admin_id": parent_id,
                    "reason": reason,
                })
                continue

            status = (
                "CONSERVATION_PASS"
                if check_conservation
                else validation_status
            )
            for row in parent_crop_rows.values():
                row["hierarchy_validation_status"] = status
            for row in parent_zone_children:
                row["hierarchy_validation_status"] = status
            accepted.extend(parent_crop_rows.values())
            accepted.extend(parent_zone_children)
            accepted_groups.append({
                **label,
                "parent_level": parent_level,
                "child_level": child_level,
                "parent_admin_id": parent_id,
                "child_zone_count": len(child_ids),
                "parent_rows": len(parent_crop_rows),
                "child_rows": len(parent_zone_children),
                "crop_count": len(EXPECTED_CROPS),
                "validation_status": status,
                "max_relative_differences": max_relative,
                "max_weighted_yield_difference_t_ha": max_yield_difference,
                "status": "PASS" if check_conservation else "LINKED_ONLY",
            })

        if len(accepted) == country_accepted_before:
            rejected_groups.append({
                **label,
                "parent_admin_id": None,
                "reason": "No parent zone passed hierarchy validation",
            })

    if rejected_groups and not allow_partial_countries:
        raise ValueError(
            f"Hierarchy validation rejected {len(rejected_groups)} parent group(s): "
            + json.dumps(rejected_groups[:10], ensure_ascii=False)
        )
    if not accepted:
        raise ValueError("No parent/child group passed MAPSPAM hierarchy validation")

    countries_passed = sorted({row["country_iso3"] for row in accepted})
    countries_all = sorted({item[0] for item in scopes})
    countries_rejected = sorted(set(countries_all) - set(countries_passed))
    statuses = sorted({row["validation_status"] for row in accepted_groups})
    report_status = (
        "PARTIAL" if rejected_groups
        else "PASS" if statuses == ["CONSERVATION_PASS"]
        else "LINKED_ONLY"
    )
    strict_reports = [
        row for row in accepted_groups
        if row["validation_status"] == "CONSERVATION_PASS"
    ]
    report = {
        "status": report_status,
        "parent_level": parent_level,
        "child_level": child_level,
        "countries_total": len(countries_all),
        "countries_passed": countries_passed,
        "countries_rejected": countries_rejected,
        "parent_groups_total": len(accepted_groups) + len(rejected_groups),
        "parent_groups_passed": len(accepted_groups),
        "parent_groups_rejected": len(rejected_groups),
        "validation_statuses": statuses,
        "parent_rows": sum(row["parent_rows"] for row in accepted_groups),
        "child_rows": sum(row["child_rows"] for row in accepted_groups),
        "accepted_rows": len(accepted),
        "crop_count": len(EXPECTED_CROPS),
        "max_relative_differences": {
            field: max(
                (
                    row["max_relative_differences"][field]
                    for row in strict_reports
                    if row["max_relative_differences"] is not None
                ),
                default=0.0,
            )
            for field in SUM_FIELDS
        },
        "max_weighted_yield_difference_t_ha": max(
            (
                row["max_weighted_yield_difference_t_ha"]
                for row in strict_reports
                if row["max_weighted_yield_difference_t_ha"] is not None
            ),
            default=0.0,
        ),
        "rejected_groups": rejected_groups,
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
    parser.add_argument(
        "--allow-unreconciled-boundaries",
        action="store_true",
        help="Store complete parent-linked summaries when administrative boundary vintages differ or are unknown; status is explicit.",
    )
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
        allow_unreconciled_boundaries=args.allow_unreconciled_boundaries,
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
