import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from backend.app.services.global_raster_zonal import aggregate_mapspam_zone


def _write_mapspam_layer(path, values):
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


def test_mapspam_zonal_summary_uses_native_units_and_weighted_yield(tmp_path):
    data_dir = tmp_path / "global-data"
    root = data_dir / "mapspam-2020-v2r2"
    root.mkdir(parents=True)

    _write_mapspam_layer(
        root / "spam2020-physical_area-all.tif",
        [[1, 2], [3, 4]],
    )
    _write_mapspam_layer(
        root / "spam2020-harvested_area-all.tif",
        [[1, 2], [3, 4]],
    )
    _write_mapspam_layer(
        root / "spam2020-production-all.tif",
        [[2, 8], [15, 24]],
    )
    _write_mapspam_layer(
        root / "spam2020-yield-all.tif",
        [[2000, 4000], [5000, 6000]],
    )

    geometry = {
        "type": "Polygon",
        "coordinates": [[
            [0, 0], [2, 0], [2, 2], [0, 2], [0, 0]
        ]],
    }
    result = aggregate_mapspam_zone(
        geometry=geometry,
        crop_band=1,
        data_dir=data_dir,
        technology="all",
    )

    assert result["valid_cells"] == 4
    assert result["physical_area_ha"] == pytest.approx(10)
    assert result["harvested_area_ha"] == pytest.approx(10)
    assert result["production_t"] == pytest.approx(49)
    assert result["yield_kg_ha_area_weighted"] == pytest.approx(4900)
    assert result["yield_t_ha_area_weighted"] == pytest.approx(4.9)
    assert result["yield_kg_ha_from_production_area"] == pytest.approx(4900)
    assert result["yield_crosscheck_abs_kg_ha"] == pytest.approx(0)


def test_mapspam_zonal_rejects_unknown_crop_band(tmp_path):
    with pytest.raises(ValueError, match="1 to 46"):
        aggregate_mapspam_zone(
            geometry={"type": "Polygon", "coordinates": []},
            crop_band=47,
            data_dir=tmp_path,
        )


def test_mapspam_zonal_rejects_unknown_technology(tmp_path):
    with pytest.raises(ValueError, match="technology"):
        aggregate_mapspam_zone(
            geometry={"type": "Polygon", "coordinates": []},
            crop_band=1,
            data_dir=tmp_path,
            technology="all-plus-irrigated",
        )
