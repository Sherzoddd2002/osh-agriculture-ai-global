from backend.app.services.global_raster_catalog import (
    CROPGRIDS, MAPSPAM, MAPSPAM_CROPS, mapspam_cog_assets,
)


def test_global_raster_catalog_has_verified_source_metadata():
    assert CROPGRIDS["expected_size_bytes"] == 806855203
    assert CROPGRIDS["license"] == "CC BY 4.0"
    assert MAPSPAM["reference_year"] == 2020
    assert MAPSPAM["crop_count"] == 46
    assert len(MAPSPAM_CROPS) == 46


def test_mapspam_catalog_exposes_12_cogs_and_crop_metadata():
    assets = mapspam_cog_assets()
    assert len(assets) == 13
    cog_assets = [x for x in assets if x["asset_id"] != "crop-codes"]
    assert len(cog_assets) == 12
    assert {x["variable"] for x in cog_assets} == {
        "physical_area", "harvested_area", "production", "yield"
    }
    assert {x["technology"] for x in cog_assets} == {
        "all", "irrigated", "rainfed"
    }


def test_yield_is_not_declared_as_additive():
    assert MAPSPAM["variables"]["yield"]["aggregation"] == "harvested-area-weighted mean"
    assert MAPSPAM["variables"]["production"]["aggregation"] == "sum"
