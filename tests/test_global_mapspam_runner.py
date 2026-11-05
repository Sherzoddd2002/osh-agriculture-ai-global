import csv
import json
from types import SimpleNamespace

from backend.app import run_global_mapspam as runner


def _polygon(x: float, y: float) -> dict:
    return {
        "type": "Polygon",
        "coordinates": [[
            [x, y], [x + 0.5, y], [x + 0.5, y + 0.5],
            [x, y + 0.5], [x, y],
        ]],
    }


def _fake_boundary():
    return {
        "metadata": {"boundaryYearRepresented": 2017},
        "geojson": {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"shapeName": "Tashkent", "shapeID": "UZB-ADM1-01"},
                    "geometry": _polygon(1, 1),
                },
                {
                    "type": "Feature",
                    "properties": {"shapeName": "Samarkand", "shapeID": "UZB-ADM1-02"},
                    "geometry": _polygon(2, 2),
                },
            ],
        },
    }


def _fake_summaries(technology: str):
    return [
        {
            "crop_band": band,
            "dataset_id": "mapspam-2020-v2r2",
            "reference_year": 2020,
            "technology": technology,
            "physical_area_ha": 10.0,
            "harvested_area_ha": 9.0,
            "production_t": 30.0,
            "yield_t_ha_area_weighted": 3.333333,
            "valid_cells": 1,
            "yield_crosscheck_abs_kg_ha": 0.0,
        }
        for band in range(1, len(runner.MAPSPAM_CROPS) + 1)
    ]


def test_adm1_resume_skips_completed_zones_and_deduplicates_csv(monkeypatch, tmp_path):
    output = tmp_path / "results"
    monkeypatch.setattr(runner, "_countries", lambda: [("UZB", "Uzbekistan")])
    monkeypatch.setattr(
        runner,
        "_load_boundary",
        lambda client, iso3, level, cache: (_fake_boundary(), "test-source"),
    )

    fail_second_zone = {"enabled": True}

    def aggregate(geometry, data_dir, technology="all"):
        first_x = geometry["coordinates"][0][0][0]
        if first_x == 2 and fail_second_zone["enabled"]:
            raise RuntimeError("simulated interruption in second admin zone")
        return _fake_summaries(technology)

    monkeypatch.setattr(runner, "aggregate_mapspam_zone_all_crops", aggregate)

    args = SimpleNamespace(
        data_dir=str(tmp_path / "global-data"),
        output_dir=str(output),
        level="ADM1",
        countries="UZB",
        technology="all",
        resume=True,
    )

    # First attempt completes Tashkent and fails while processing Samarkand.
    runner.run(args)

    summary_path = output / "mapspam_2020_adm1.csv"
    checkpoint_path = output / "mapspam_2020_adm1_completed.json"

    with summary_path.open("r", newline="", encoding="utf-8-sig") as file:
        first_rows = list(csv.DictReader(file))
    assert len(first_rows) == len(runner.MAPSPAM_CROPS)

    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint == ["UZB::UZB-ADM1-01"]

    # Restart succeeds: completed Tashkent must not be recomputed or duplicated.
    fail_second_zone["enabled"] = False
    runner.run(args)

    with summary_path.open("r", newline="", encoding="utf-8-sig") as file:
        final_rows = list(csv.DictReader(file))

    expected_rows = 2 * len(runner.MAPSPAM_CROPS)
    assert len(final_rows) == expected_rows

    identities = {
        (row["country_iso3"], row["admin_id"], row["technology"], row["crop_code"])
        for row in final_rows
    }
    assert len(identities) == expected_rows
    assert {row["admin_id"] for row in final_rows} == {
        "UZB-ADM1-01",
        "UZB-ADM1-02",
    }

    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert checkpoint == ["UZB::UZB-ADM1-01", "UZB::UZB-ADM1-02"]
