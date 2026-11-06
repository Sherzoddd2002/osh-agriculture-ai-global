import csv
import json
from pathlib import Path

import pytest
from types import SimpleNamespace

from backend.app import run_global_mapspam_hierarchy as runner
from backend.app.import_mapspam_hierarchy import validate_adjacent_levels
from backend.app.import_mapspam_results import _read_level
from backend.app.services.global_raster_catalog import MAPSPAM_CROPS


CSV_FIELDS = [
    "country_iso3", "country_name", "admin_level", "admin_name", "admin_id",
    "parent_admin_level", "parent_admin_id", "parent_boundary_source",
    "parent_boundary_year", "parent_link_method", "parent_link_distance_deg",
    "boundary_source", "boundary_year",
    "dataset_id", "source_year", "technology", "crop_code", "crop_name",
    "crop_band", "physical_area_ha", "harvested_area_ha", "production_t",
    "yield_t_ha_area_weighted", "valid_cells",
    "yield_crosscheck_abs_kg_ha", "spatial_status", "computed_at_utc",
]


def _polygon(x1, y1, x2, y2):
    return {
        "type": "Polygon",
        "coordinates": [[
            [x1, y1], [x2, y1], [x2, y2], [x1, y2], [x1, y1],
        ]],
    }


def _summary_rows(technology="all"):
    return [
        {
            "crop_band": band,
            "dataset_id": "mapspam-2020-v2r2",
            "reference_year": 2020,
            "technology": technology,
            "physical_area_ha": 10.0,
            "harvested_area_ha": 8.0,
            "production_t": 16.0,
            "yield_t_ha_area_weighted": 2.0,
            "valid_cells": 1,
            "yield_crosscheck_abs_kg_ha": 0.0,
        }
        for band in range(1, len(MAPSPAM_CROPS) + 1)
    ]


def test_child_polygon_is_linked_to_covering_parent():
    parents = [{
        "id": "UZB-ADM1-01",
        "_shape": runner.shape(_polygon(0, 0, 2, 2)),
    }]
    child = _polygon(0.25, 0.25, 0.75, 0.75)

    assert runner._assign_parent_id(child, parents) == "UZB-ADM1-01"


def test_child_polygon_uses_largest_intersection_when_boundaries_do_not_nest():
    child = _polygon(0.5, 0.5, 1.5, 1.5)
    parents = [
        {"id": "P1", "_shape": runner.shape(_polygon(0, 0, 1, 2))},
        {"id": "P2", "_shape": runner.shape(_polygon(1, 0, 2, 2))},
    ]

    assert runner._assign_parent_id(child, parents) == "P1"


def test_child_outside_parent_uses_limited_nearest_parent_fallback():
    parents = [{
        "id": "UZB-ADM1-01",
        "_shape": runner.shape(_polygon(0, 0, 1, 1)),
    }]
    child = _polygon(1.01, 0.2, 1.02, 0.3)

    assert runner._assign_parent_id(child, parents) == "UZB-ADM1-01"


def test_child_far_from_all_parents_is_rejected():
    parents = [{
        "id": "UZB-ADM1-01",
        "_shape": runner.shape(_polygon(0, 0, 1, 1)),
    }]
    child = _polygon(2, 2, 2.1, 2.1)

    try:
        runner._assign_parent_id(child, parents)
    except ValueError as exc:
        assert "outside the limited snap tolerance" in str(exc)
    else:
        raise AssertionError("A remote child polygon was assigned to a parent")


def test_adm2_runner_writes_parent_lineage_and_resumes(monkeypatch, tmp_path):
    output = tmp_path / "results"
    boundaries = {
        "ADM2": {
            "metadata": {"boundaryYearRepresented": 2021},
            "geojson": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"shapeName": "District A", "shapeID": "UZB-D2-A"},
                        "geometry": _polygon(0.1, 0.1, 0.9, 0.9),
                    },
                    {
                        "type": "Feature",
                        "properties": {"shapeName": "District B", "shapeID": "UZB-D2-B"},
                        "geometry": _polygon(1.1, 1.1, 1.9, 1.9),
                    },
                ],
            },
        },
        "ADM1": {
            "metadata": {"boundaryYearRepresented": 2021},
            "geojson": {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {"shapeName": "Region", "shapeID": "UZB-D1-01"},
                        "geometry": _polygon(0, 0, 2, 2),
                    }
                ],
            },
        },
    }

    monkeypatch.setattr(runner, "_countries", lambda: [("UZB", "Uzbekistan")])
    monkeypatch.setattr(
        runner,
        "_load_boundary",
        lambda client, iso3, level, cache: (boundaries[level], "test-source"),
    )
    monkeypatch.setattr(
        runner,
        "aggregate_mapspam_zone_all_crops",
        lambda geometry, data_dir, technology="all": _summary_rows(technology),
    )

    args = SimpleNamespace(
        level="ADM2",
        countries="UZB",
        data_dir=str(tmp_path / "data"),
        output_dir=str(output),
        technology="all",
        timeout=10,
        error_delay=0,
        resume=True,
    )
    runner.run(args)

    csv_path = output / "mapspam_2020_adm2.csv"
    with csv_path.open("r", newline="", encoding="utf-8-sig") as stream:
        rows = list(csv.DictReader(stream))

    assert len(rows) == 2 * len(MAPSPAM_CROPS)
    assert {row["parent_admin_level"] for row in rows} == {"ADM1"}
    assert {row["parent_admin_id"] for row in rows} == {"UZB-D1-01"}
    assert {row["parent_boundary_year"] for row in rows} == {"2021"}
    assert {row["parent_link_method"] for row in rows} == {"POINT_CONTAINMENT"}
    checkpoint = json.loads(
        (output / "mapspam_2020_adm2_completed.json").read_text(encoding="utf-8")
    )
    assert checkpoint == ["UZB::UZB-D2-A", "UZB::UZB-D2-B"]

    # A second run must not add duplicate rows.
    runner.run(args)
    with csv_path.open("r", newline="", encoding="utf-8-sig") as stream:
        assert len(list(csv.DictReader(stream))) == 2 * len(MAPSPAM_CROPS)


def _row(country, level, admin_id, parent_level, parent_id, band, crop_code, crop_name, values):
    no_cells = band == len(MAPSPAM_CROPS)
    return {
        "country_iso3": country,
        "country_name": "Uzbekistan",
        "admin_level": level,
        "admin_name": admin_id,
        "admin_id": admin_id,
        "parent_admin_level": parent_level or "",
        "parent_admin_id": parent_id or "",
        "parent_boundary_source": "gbOpen" if level in {"ADM2", "ADM3", "ADM4"} else "",
        "parent_boundary_year": "2021" if level in {"ADM2", "ADM3", "ADM4"} else "",
        "parent_link_method": "POINT_CONTAINMENT" if level in {"ADM2", "ADM3", "ADM4"} else "",
        "parent_link_distance_deg": "0" if level in {"ADM2", "ADM3", "ADM4"} else "",
        "boundary_source": "gbOpen",
        "boundary_year": "2021",
        "dataset_id": "mapspam-2020-v2r2",
        "source_year": "2020",
        "technology": "all",
        "crop_code": crop_code,
        "crop_name": crop_name,
        "crop_band": str(band),
        "physical_area_ha": str(values[0]),
        "harvested_area_ha": str(values[1]),
        "production_t": str(values[2]),
        "yield_t_ha_area_weighted": "" if no_cells else str(values[3]),
        "valid_cells": str(values[4]),
        "yield_crosscheck_abs_kg_ha": "" if no_cells else "0",
        "spatial_status": "NO_RASTER_CELLS" if no_cells else "ESTIMATED",
        "computed_at_utc": "2026-11-06T00:00:00+00:00",
    }


def test_adjacent_level_validation_checks_all_children_against_parent(tmp_path):
    parent_path = tmp_path / "adm1.csv"
    child_path = tmp_path / "adm2.csv"
    parent_rows = []
    child_rows = []

    for band, (crop_code, crop_name) in enumerate(MAPSPAM_CROPS, 1):
        no_cells = band == len(MAPSPAM_CROPS)
        child_values = (0, 0, 0, None, 0) if no_cells else (50, 40, 80, 2, 1)
        parent_values = (0, 0, 0, None, 0) if no_cells else (100, 80, 160, 2, 2)
        parent_rows.append(
            _row("UZB", "ADM1", "UZB-R1", "ADM0", "UZB", band, crop_code, crop_name, parent_values)
        )
        for child_id in ("UZB-D1", "UZB-D2"):
            child_rows.append(
                _row("UZB", "ADM2", child_id, "ADM1", "UZB-R1", band, crop_code, crop_name, child_values)
            )

    for path, rows in ((parent_path, parent_rows), (child_path, child_rows)):
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    parents = _read_level(parent_path, "ADM1")
    children = _read_level(child_path, "ADM2")
    accepted, report = validate_adjacent_levels(parents, children, "ADM1", "ADM2")

    assert report["status"] == "PASS"
    assert report["countries_passed"] == ["UZB"]
    assert report["child_rows"] == 2 * len(MAPSPAM_CROPS)
    assert len(accepted) == 3 * len(MAPSPAM_CROPS)


@pytest.mark.parametrize(
    ("parent_level", "child_level"),
    [("ADM2", "ADM3"), ("ADM3", "ADM4")],
)
def test_importer_supports_adm3_and_adm4_adjacent_levels(
    tmp_path, parent_level, child_level
):
    parent_path = tmp_path / f"{parent_level.lower()}.csv"
    child_path = tmp_path / f"{child_level.lower()}.csv"
    parent_rows = []
    child_rows = []
    parent_id = f"UZB-{parent_level}-P1"
    parent_parent_level = f"ADM{int(parent_level[-1]) - 1}"

    for band, (crop_code, crop_name) in enumerate(MAPSPAM_CROPS, 1):
        no_cells = band == len(MAPSPAM_CROPS)
        child_values = (0, 0, 0, None, 0) if no_cells else (50, 40, 80, 2, 1)
        parent_values = (0, 0, 0, None, 0) if no_cells else (100, 80, 160, 2, 2)
        parent_rows.append(
            _row(
                "UZB", parent_level, parent_id, parent_parent_level,
                f"UZB-{parent_parent_level}-P0",
                band, crop_code, crop_name, parent_values,
            )
        )
        for index in (1, 2):
            child_rows.append(
                _row(
                    "UZB", child_level, f"UZB-{child_level}-C{index}",
                    parent_level, parent_id, band, crop_code, crop_name,
                    child_values,
                )
            )

    for file_path, rows in ((parent_path, parent_rows), (child_path, child_rows)):
        with file_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    parents = _read_level(parent_path, parent_level)
    children = _read_level(child_path, child_level)
    accepted, report = validate_adjacent_levels(
        parents, children, parent_level, child_level
    )

    assert report["status"] == "PASS"
    assert report["parent_level"] == parent_level
    assert report["child_level"] == child_level
    assert report["child_rows"] == 2 * len(MAPSPAM_CROPS)
    assert len(accepted) == 3 * len(MAPSPAM_CROPS)


def test_vintage_mismatch_is_explicitly_linked_without_claiming_conservation(tmp_path):
    parent_path = tmp_path / "adm1.csv"
    child_path = tmp_path / "adm2.csv"
    parent_rows = []
    child_rows = []

    for band, (crop_code, crop_name) in enumerate(MAPSPAM_CROPS, 1):
        no_cells = band == len(MAPSPAM_CROPS)
        child_values = (0, 0, 0, None, 0) if no_cells else (1, 1, 1, 1, 1)
        parent_values = (0, 0, 0, None, 0) if no_cells else (100, 80, 160, 2, 2)
        parent_rows.append(
            _row("UZB", "ADM1", "UZB-R1", "ADM0", "UZB", band, crop_code, crop_name, parent_values)
        )
        for child_id in ("UZB-D1", "UZB-D2"):
            row = _row(
                "UZB", "ADM2", child_id, "ADM1", "UZB-R1",
                band, crop_code, crop_name, child_values
            )
            row["boundary_year"] = "2020"
            row["parent_boundary_year"] = "2017"
            child_rows.append(row)

    for row in parent_rows:
        row["boundary_year"] = "2017"

    for path, rows in ((parent_path, parent_rows), (child_path, child_rows)):
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    parents = _read_level(parent_path, "ADM1")
    children = _read_level(child_path, "ADM2")

    try:
        validate_adjacent_levels(parents, children, "ADM1", "ADM2")
    except ValueError as exc:
        assert "allow-unreconciled-boundaries" in str(exc)
    else:
        raise AssertionError("Vintage mismatch must not be silently accepted")

    accepted, report = validate_adjacent_levels(
        parents,
        children,
        "ADM1",
        "ADM2",
        allow_unreconciled_boundaries=True,
    )
    assert report["status"] == "LINKED_ONLY"
    assert report["validation_statuses"] == [
        "BOUNDARY_VINTAGE_MISMATCH_NOT_RECONCILED"
    ]
    assert len(accepted) == 3 * len(MAPSPAM_CROPS)
    assert {
        row["hierarchy_validation_status"] for row in accepted
    } == {"BOUNDARY_VINTAGE_MISMATCH_NOT_RECONCILED"}


def test_adjacent_level_validation_rejects_nonconserving_parent(tmp_path):
    parent_path = tmp_path / "adm1.csv"
    child_path = tmp_path / "adm2.csv"
    parent_rows = []
    child_rows = []

    for band, (crop_code, crop_name) in enumerate(MAPSPAM_CROPS, 1):
        no_cells = band == len(MAPSPAM_CROPS)
        child_values = (0, 0, 0, None, 0) if no_cells else (50, 40, 80, 2, 1)
        parent_values = (0, 0, 0, None, 0) if no_cells else (100, 80, 160, 2, 2)
        if band == 1:
            parent_values = (999, 80, 160, 2, 2)
        parent_rows.append(
            _row("UZB", "ADM1", "UZB-R1", "ADM0", "UZB", band, crop_code, crop_name, parent_values)
        )
        for child_id in ("UZB-D1", "UZB-D2"):
            child_rows.append(
                _row("UZB", "ADM2", child_id, "ADM1", "UZB-R1", band, crop_code, crop_name, child_values)
            )

    for path, rows in ((parent_path, parent_rows), (child_path, child_rows)):
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    parents = _read_level(parent_path, "ADM1")
    children = _read_level(child_path, "ADM2")
    try:
        validate_adjacent_levels(parents, children, "ADM1", "ADM2")
    except ValueError as exc:
        assert "physical_area_ha" in str(exc)
    else:
        raise AssertionError("Non-conserving parent/child values were accepted")
