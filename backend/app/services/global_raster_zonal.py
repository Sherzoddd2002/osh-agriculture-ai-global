"""Windowed zonal summaries for MAPSPAM COG assets.

Requires optional rasterio. Every read is limited to a raster block intersecting
the selected administrative polygon; no global raster is materialized in memory.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def _valid(values, nodata):
    import numpy as np
    mask = np.isfinite(values)
    if nodata is not None:
        mask &= values != nodata
    return mask


def aggregate_mapspam_zone(
    geometry: dict[str, Any],
    crop_band: int,
    data_dir: str | Path,
    technology: str = "all",
) -> dict:
    """Aggregate one polygon and one crop band from local MAPSPAM COG files.

    MAPSPAM area and production bands are in thousand hectares and thousand
    tonnes respectively. Yield is kg/ha and is weighted by harvested area.
    """
    try:
        import numpy as np
        import rasterio
        from rasterio.features import geometry_mask
        from rasterio.windows import from_bounds
    except ImportError as exc:
        raise RuntimeError("Install rasterio to run global raster zonal summaries") from exc

    if not 1 <= int(crop_band) <= 46:
        raise ValueError("MAPSPAM crop_band must be between 1 and 46")
    if technology not in {"all", "irrigated", "rainfed"}:
        raise ValueError("technology must be all, irrigated or rainfed")

    root = Path(data_dir) / "mapspam-2020-v2r2"
    names = {
        "physical_area": f"spam2020-physical_area-{technology}.tif",
        "harvested_area": f"spam2020-harvested_area-{technology}.tif",
        "production": f"spam2020-production-{technology}.tif",
        "yield": f"spam2020-yield-{technology}.tif",
    }
    paths = {key: root / name for key, name in names.items()}
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing MAPSPAM assets: " + ", ".join(missing))

    sums = {"physical_area_1000_ha": 0.0, "harvested_area_1000_ha": 0.0,
            "production_1000_t": 0.0, "yield_weighted_sum": 0.0,
            "yield_weight_1000_ha": 0.0}
    valid_cells = 0
    with rasterio.open(paths["harvested_area"]) as ref:
        if ref.crs is None:
            raise ValueError("MAPSPAM raster CRS is missing")
        geom = geometry
        if ref.crs.to_string() != "EPSG:4326":
            from rasterio.warp import transform_geom
            geom = transform_geom("EPSG:4326", ref.crs, geometry)
        bounds = rasterio.features.bounds(geom)
        window = from_bounds(*bounds, transform=ref.transform)
        window = window.round_offsets().round_lengths()
        window = window.intersection(rasterio.windows.Window(0, 0, ref.width, ref.height))
        if window.width <= 0 or window.height <= 0:
            raise ValueError("Selected geometry does not intersect MAPSPAM raster")

        datasets = {key: rasterio.open(path) for key, path in paths.items()}
        try:
            for _, block_window in ref.block_windows(crop_band):
                overlap = block_window.intersection(window)
                if overlap.width <= 0 or overlap.height <= 0:
                    continue
                transform = ref.window_transform(overlap)
                inside = geometry_mask([geom], out_shape=(int(overlap.height), int(overlap.width)),
                                       transform=transform, invert=True, all_touched=False)
                arrays = {key: ds.read(crop_band, window=overlap, masked=False)
                          for key, ds in datasets.items()}
                masks = {key: _valid(arr, datasets[key].nodata) & inside
                         for key, arr in arrays.items()}
                joint = masks["harvested_area"] & masks["production"]
                # Only positive harvested area contributes to yield weights.
                joint &= arrays["harvested_area"] > 0
                if not joint.any():
                    continue
                valid_cells += int(joint.sum())
                for key, out_key in (("physical_area", "physical_area_1000_ha"),
                                     ("harvested_area", "harvested_area_1000_ha"),
                                     ("production", "production_1000_t")):
                    valid = masks[key]
                    sums[out_key] += float(arrays[key][valid].sum(dtype="float64"))
                weights = arrays["harvested_area"][joint].astype("float64")
                yields = arrays["yield"][joint].astype("float64")
                yield_valid = masks["yield"][joint] & np.isfinite(yields)
                sums["yield_weighted_sum"] += float((yields[yield_valid] * weights[yield_valid]).sum())
                sums["yield_weight_1000_ha"] += float(weights[yield_valid].sum())
        finally:
            for ds in datasets.values():
                ds.close()

    total_area = sums["harvested_area_1000_ha"]
    production = sums["production_1000_t"]
    weighted_yield = (sums["yield_weighted_sum"] / sums["yield_weight_1000_ha"]
                      if sums["yield_weight_1000_ha"] else None)
    production_yield = production / total_area * 1000 if total_area > 0 else None
    return {
        "dataset_id": "mapspam-2020-v2r2",
        "reference_year": 2020,
        "technology": technology,
        "crop_band": int(crop_band),
        "valid_cells": valid_cells,
        "physical_area_ha": sums["physical_area_1000_ha"] * 1000,
        "harvested_area_ha": total_area * 1000,
        "production_t": production * 1000,
        "yield_kg_ha_area_weighted": weighted_yield,
        "yield_t_ha_from_production_area": production_yield / 1000 if production_yield is not None else None,
        "yield_crosscheck_abs_kg_ha": (
            abs(weighted_yield - production_yield) if weighted_yield is not None and production_yield is not None else None
        ),
        "units_note": "Source area is thousand ha; production is thousand tonnes; yield is kg/ha.",
        "aggregation_note": "Yield is harvested-area weighted; never sum a yield raster.",
    }
