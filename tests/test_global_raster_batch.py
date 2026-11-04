import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from backend.app.services.global_raster_batch import (
    aggregate_mapspam_zone_all_crops,
)


def _write_layer(path, values):
    profile = {
        "driver": "GTiff",
        "height": 2,
        "width": 2,
        "count": 46,
        "dtype": "float32",
        "crs": "EPSG:4326",
        "transform": from_origin(0, 2, 1, 1),
        "nodata": -9999.0,
    }
    bands = np.full((46, 2, 2), -9999.0, dtype="float32")
    bands[0] = np.asarray(values, dtype="float32")
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(bands)


def test_all_crop_batch_matches_expected_native_unit_summary(tmp_path):
    root = tmp_path / "global-data" / "mapspam-2020-v2r2"
    root.mkdir(parents=True)
    _write_layer(root / "spam2020-physical_area-all.tif", [[1, 2], [3, 4]])
    _write_layer(root / "spam2020-harvested_area-all.tif", [[1, 2], [3, 4]])
    _write_layer(root / "spam2020-production-all.tif", [[2, 8], [15, 24]])
    _write_layer(root / "spam2020-yield-all.tif", [[2000, 4000], [5000, 6000]])

    geometry = {
        "type": "Polygon",
        "coordinates": [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]],
    }
    results = aggregate_mapspam_zone_all_crops(geometry, tmp_path / "global-data")

    assert len(results) == 46
    wheat = results[0]
    assert wheat["crop_band"] == 1
    assert wheat["valid_cells"] == 4
    assert wheat["physical_area_ha"] == pytest.approx(10)
    assert wheat["harvested_area_ha"] == pytest.approx(10)
    assert wheat["production_t"] == pytest.approx(49)
    assert wheat["yield_t_ha_area_weighted"] == pytest.approx(4.9)
    assert wheat["yield_crosscheck_abs_kg_ha"] == pytest.approx(0)

    empty_crop = results[1]
    assert empty_crop["valid_cells"] == 0
    assert empty_crop["production_t"] == pytest.approx(0)
    assert empty_crop["yield_t_ha_area_weighted"] is None


def test_all_crop_batch_rejects_invalid_technology(tmp_path):
    with pytest.raises(ValueError, match="technology"):
        aggregate_mapspam_zone_all_crops(
            {"type": "Polygon", "coordinates": []},
            tmp_path,
            technology="unknown",
        )
