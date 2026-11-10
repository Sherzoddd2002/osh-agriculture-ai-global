from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from scripts.export_public_mapspam_global import (  # noqa: E402
    CROP_CODES,
    count_summary_rows,
    merge_uzb_adm2_reference,
)


def _crop_rows() -> dict:
    return {
        code: {
            "physical_area_ha": 10.0,
            "harvested_area_ha": 8.0,
            "production_t": 16.0,
            "yield_t_ha": 2.0,
            "valid_cells": 2,
            "spatial_status": "ESTIMATED",
            "yield_crosscheck_abs_kg_ha": 0.0,
        }
        for code in CROP_CODES
    }


def _fixture(tmp_path: Path):
    output_dir = tmp_path / "global"
    output_dir.mkdir()
    provinces = {
        f"UZB-P{index:02d}": {
            "name": f"Province {index}",
            "parent_admin_id": "UZB",
            "boundary_year": 2017,
            "crops": _crop_rows(),
        }
        for index in range(14)
    }
    districts = {
        f"UZB-D{index:03d}": {
            "name": f"District {index}",
            "parent_admin_id": f"UZB-P{index % 14:02d}",
            "crops": _crop_rows(),
        }
        for index in range(199)
    }
    reference = {
        "country_iso3": "UZB",
        "dataset_id": "mapspam-2020-v2r2",
        "source_year": 2020,
        "technology": "all",
        "license": "CC BY-SA 4.0",
        "source_url": "https://doi.org/10.7910/DVN/SWPENT",
        "levels": {
            "ADM1": {
                "boundary_year": 2017,
                "area_count": 14,
                "crop_count": 46,
                "areas": provinces,
            },
            "ADM2": {
                "boundary_year": 2020,
                "area_count": 199,
                "crop_count": 46,
                "areas": districts,
            },
        },
    }
    reference_path = output_dir.parent / "UZB_MAPSPAM_2020_ADM1_ADM2.json"
    reference_path.write_text(json.dumps(reference), encoding="utf-8")
    payload = {
        "country_iso3": "UZB",
        "levels": {
            "ADM0": {
                "areas": {
                    "UZB": {"name": "Uzbekistan", "crops": _crop_rows()}
                }
            },
            "ADM1": {
                "area_count": 14,
                "crop_count": 46,
                "areas": provinces,
            },
        },
    }
    return output_dir, payload, districts, provinces


def test_uzb_global_package_keeps_validated_199_districts(tmp_path):
    output_dir, payload, districts, provinces = _fixture(tmp_path)

    merged = merge_uzb_adm2_reference(payload, output_dir)

    assert merged["levels"]["ADM2"]["area_count"] == 199
    assert set(merged["levels"]["ADM2"]["areas"]) == set(districts)
    assert {
        row["parent_admin_id"]
        for row in merged["levels"]["ADM2"]["areas"].values()
    } == set(provinces)
    assert merged["uzbekistan_adm2_reference"]["district_count"] == 199
    assert count_summary_rows(merged) == (1 + 14 + 199) * 46


def test_uzb_global_package_rejects_unknown_district_parent(tmp_path):
    output_dir, payload, districts, _ = _fixture(tmp_path)
    reference_path = output_dir.parent / "UZB_MAPSPAM_2020_ADM1_ADM2.json"
    reference = json.loads(reference_path.read_text(encoding="utf-8"))
    first_district = next(iter(reference["levels"]["ADM2"]["areas"].values()))
    first_district["parent_admin_id"] = "UZB-UNKNOWN"
    reference_path.write_text(json.dumps(reference), encoding="utf-8")

    with pytest.raises(ValueError, match="parent IDs"):
        merge_uzb_adm2_reference(payload, output_dir)


def test_non_uzbekistan_package_is_not_modified(tmp_path):
    payload = {"country_iso3": "KAZ", "levels": {"ADM1": {"areas": {}}}}
    assert merge_uzb_adm2_reference(payload, tmp_path / "global") is payload
