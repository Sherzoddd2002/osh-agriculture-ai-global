"""Windowed, area-correct zonal summaries for MAPSPAM 2020 COG assets.

The global rasters remain on disk. Only the blocks intersecting a supplied
administrative polygon are read into memory.
"""
from __future__ import annotations

from contextlib import ExitStack
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
    """Summarize one MAPSPAM crop band inside a GeoJSON polygon.

    Official MAPSPAM COG units are physical_area=ha, harvested_area=ha,
    production=t, and yield=kg/ha. Yield is aggregated with harvested area
    as the weight; it must never be summed.
    """
    try:
        import numpy as np
        import rasterio
        from rasterio.features import bounds, geometry_mask
        from rasterio.windows import Window, from_bounds
    except ImportError as exc:
        raise RuntimeError("Raster summaries require rasterio>=1.5") from exc

    if not isinstance(crop_band, int) or not 1 <= crop_band <= 46:
        raise ValueError("MAPSPAM crop_band must be an integer from 1 to 46")
    if technology not in {"all", "irrigated", "rainfed"}:
        raise ValueError("technology must be all, irrigated or rainfed")

    root = Path(data_dir) / "mapspam-2020-v2r2"
    paths = {
        "physical_area": root / f"spam2020-physical_area-{technology}.tif",
        "harvested_area": root / f"spam2020-harvested_area-{technology}.tif",
        "production": root / f"spam2020-production-{technology}.tif",
        "yield": root / f"spam2020-yield-{technology}.tif",
    }
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing MAPSPAM assets: " + ", ".join(missing))

    totals = {
        "physical_area_ha": 0.0,
        "harvested_area_ha": 0.0,
        "production_t": 0.0,
        "yield_area_weighted_sum": 0.0,
        "yield_weight_ha": 0.0,
    }
    valid_harvested_cells = 0

    with ExitStack() as stack:
        datasets = {
            key: stack.enter_context(rasterio.open(path))
            for key, path in paths.items()
        }
        ref = datasets["harvested_area"]
        if ref.crs is None:
            raise ValueError("MAPSPAM raster CRS is missing")
        if ref.count < crop_band:
            raise ValueError(f"MAPSPAM raster has only {ref.count} bands")

        for key, ds in datasets.items():
            if (
                ds.width != ref.width
                or ds.height != ref.height
                or ds.count < crop_band
                or ds.crs != ref.crs
                or ds.transform != ref.transform
            ):
                raise ValueError(f"MAPSPAM {key} raster grid does not match harvested_area")

        geom = geometry
        if ref.crs.to_string() != "EPSG:4326":
            from rasterio.warp import transform_geom

            geom = transform_geom("EPSG:4326", ref.crs, geometry)

        raster_bounds = bounds(geom)
        window = from_bounds(*raster_bounds, transform=ref.transform)
        window = window.round_offsets().round_lengths()
        try:
            window = window.intersection(Window(0, 0, ref.width, ref.height))
        except Exception as exc:
            raise ValueError("Selected geometry does not intersect MAPSPAM raster") from exc
        if window.width <= 0 or window.height <= 0:
            raise ValueError("Selected geometry does not intersect MAPSPAM raster")

        block_height, block_width = ref.block_shapes[crop_band - 1]
        first_block_row = max(0, int(window.row_off // block_height))
        last_block_row = max(
            first_block_row,
            int((window.row_off + window.height - 1) // block_height),
        )
        first_block_col = max(0, int(window.col_off // block_width))
        last_block_col = max(
            first_block_col,
            int((window.col_off + window.width - 1) // block_width),
        )

        for block_row in range(first_block_row, last_block_row + 1):
            for block_col in range(first_block_col, last_block_col + 1):
                block = Window(
                    block_col * block_width,
                    block_row * block_height,
                    min(block_width, ref.width - block_col * block_width),
                    min(block_height, ref.height - block_row * block_height),
                )
                overlap = block.intersection(window)
                if overlap.width <= 0 or overlap.height <= 0:
                    continue

                inside = geometry_mask(
                    [geom],
                    out_shape=(int(overlap.height), int(overlap.width)),
                    transform=ref.window_transform(overlap),
                    invert=True,
                    all_touched=False,
                )
                arrays = {
                    key: ds.read(crop_band, window=overlap, masked=False)
                    for key, ds in datasets.items()
                }
                masks = {
                    key: _valid(arrays[key], datasets[key].nodata) & inside
                    for key in datasets
                }

                physical_valid = masks["physical_area"] & (arrays["physical_area"] >= 0)
                harvested_valid = masks["harvested_area"] & (arrays["harvested_area"] > 0)
                production_valid = masks["production"] & (arrays["production"] >= 0)
                yield_valid = masks["yield"] & harvested_valid & (arrays["yield"] >= 0)

                totals["physical_area_ha"] += float(
                    arrays["physical_area"][physical_valid].sum(dtype="float64")
                )
                totals["harvested_area_ha"] += float(
                    arrays["harvested_area"][harvested_valid].sum(dtype="float64")
                )
                totals["production_t"] += float(
                    arrays["production"][production_valid].sum(dtype="float64")
                )
                valid_harvested_cells += int(harvested_valid.sum())

                weights = arrays["harvested_area"][yield_valid].astype("float64")
                yields = arrays["yield"][yield_valid].astype("float64")
                totals["yield_area_weighted_sum"] += float((yields * weights).sum())
                totals["yield_weight_ha"] += float(weights.sum())

    harvested_area = totals["harvested_area_ha"]
    production = totals["production_t"]
    weighted_yield = (
        totals["yield_area_weighted_sum"] / totals["yield_weight_ha"]
        if totals["yield_weight_ha"] > 0 else None
    )
    production_yield = production / harvested_area * 1000.0 if harvested_area > 0 else None

    return {
        "dataset_id": "mapspam-2020-v2r2",
        "reference_year": 2020,
        "technology": technology,
        "crop_band": crop_band,
        "valid_cells": valid_harvested_cells,
        "physical_area_ha": totals["physical_area_ha"],
        "harvested_area_ha": harvested_area,
        "production_t": production,
        "yield_kg_ha_area_weighted": weighted_yield,
        "yield_t_ha_area_weighted": weighted_yield / 1000.0 if weighted_yield is not None else None,
        "yield_kg_ha_from_production_area": production_yield,
        "yield_crosscheck_abs_kg_ha": (
            abs(weighted_yield - production_yield)
            if weighted_yield is not None and production_yield is not None
            else None
        ),
        "units_note": "Source units: physical/harvested area=ha, production=t, yield=kg/ha.",
        "aggregation_note": "Areas and production are summed; yield is harvested-area weighted.",
    }
