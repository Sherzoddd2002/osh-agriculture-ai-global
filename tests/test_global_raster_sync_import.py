from backend.app.sync_global_rasters import MAPSPAM_CORE_ASSETS, sync_mapspam
from backend.app.services.global_raster_catalog import MAPSPAM, mapspam_cog_assets


def test_global_raster_sync_imports_catalog_from_services_package():
    assert MAPSPAM["dataset_id"] == "mapspam-2020-v2r2"
    assert MAPSPAM_CORE_ASSETS == {
        "physical_area-all",
        "harvested_area-all",
        "production-all",
        "yield-all",
    }
    assert callable(sync_mapspam)
    assert len(mapspam_cog_assets()) == 13
