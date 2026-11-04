from backend.app.services.global_raster_catalog import (
    CROPGRIDS, MAPSPAM, MAPSPAM_CROPS, catalog_summary, mapspam_cog_assets,
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


def test_mapspam_source_units_match_official_cog_metadata():
    assert MAPSPAM["variables"]["physical_area"]["unit"] == "ha"
    assert MAPSPAM["variables"]["harvested_area"]["unit"] == "ha"
    assert MAPSPAM["variables"]["production"]["unit"] == "t"
    assert MAPSPAM["variables"]["yield"]["unit"] == "kg/ha"


def test_yield_is_not_declared_as_additive():
    assert MAPSPAM["variables"]["yield"]["aggregation"] == "harvested-area-weighted mean"
    assert MAPSPAM["variables"]["production"]["aggregation"] == "sum"



def test_catalog_returns_crop_codes_names_and_one_based_raster_bands():
    crops = catalog_summary()["mapspam"]["crops"]
    assert len(crops) == 46
    assert crops[0] == {"code": "whea", "name": "Wheat", "band": 1}
    assert crops[1] == {"code": "rice", "name": "Rice", "band": 2}
    assert crops[-1]["band"] == 46
