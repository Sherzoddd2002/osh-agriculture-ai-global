"""Efficient all-crop MAPSPAM zonal summaries for batch processing.

Opens the four source COGs once per administrative polygon and calculates all
46 crop bands. Original rasters remain untouched on disk.
"""
from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from typing import Any


GRID_TOLERANCE_PIXELS = 1e-5


def _valid(values, nodata):
    import numpy as np

    mask = np.isfinite(values)
    if nodata is not None:
        mask &= values != nodata
    return mask


def _polygon_parts(geometry: dict[str, Any]) -> list[dict[str, Any]]:
    from shapely.geometry import mapping, shape

    if geometry.get("type") == "Feature":
        geometry = geometry.get("geometry") or {}
    geom = shape(geometry)
    if geom.is_empty or not geom.is_valid:
        raise ValueError("Selected boundary geometry is empty or invalid")
    if geom.geom_type == "Polygon":
        return [mapping(geom)]
    if geom.geom_type == "MultiPolygon":
        return [mapping(part) for part in geom.geoms if not part.is_empty]
    raise ValueError("Only Polygon or MultiPolygon geometries are supported")


def _validate_grid(datasets: dict, reference) -> None:
    inverse_ref = ~reference.transform
    for key, ds in datasets.items():
        compatible = (
            ds.width == reference.width
            and ds.height == reference.height
            and ds.count >= 46
            and ds.crs == reference.crs
        )
        if compatible:
            for col, row in (
                (0, 0),
                (reference.width, 0),
                (0, reference.height),
                (reference.width, reference.height),
            ):
                x, y = ds.transform * (col, row)
                ref_col, ref_row = inverse_ref * (x, y)
                if (
                    abs(ref_col - col) > GRID_TOLERANCE_PIXELS
                    or abs(ref_row - row) > GRID_TOLERANCE_PIXELS
                ):
                    compatible = False
                    break
        if not compatible:
            raise ValueError(
                f"MAPSPAM {key} raster grid does not align with "
                f"harvested_area within {GRID_TOLERANCE_PIXELS:g} pixel tolerance"
            )


def aggregate_mapspam_zone_all_crops(
    geometry: dict[str, Any],
    data_dir: str | Path,
    technology: str = "all",
) -> list[dict]:
    """Summarize all 46 MAPSPAM crop bands inside one Polygon/MultiPolygon.

    Area units are hectares, production is tonnes, and yield is kg/ha.
    Yield is averaged with harvested area as its weight, never summed.
    """
    try:
        import numpy as np
        import rasterio
        from rasterio.features import bounds, geometry_mask
        from rasterio.windows import Window, from_bounds
    except ImportError as exc:
        raise RuntimeError("Raster summaries require rasterio>=1.5") from exc

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

    bands = range(1, 47)
    totals = {
        band: {
            "physical_area_ha": 0.0,
            "harvested_area_ha": 0.0,
            "production_t": 0.0,
            "yield_area_weighted_sum": 0.0,
            "yield_weight_ha": 0.0,
            "valid_cells": 0,
        }
        for band in bands
    }

    polygons = _polygon_parts(geometry)

    with ExitStack() as stack:
        datasets = {
            key: stack.enter_context(rasterio.open(path))
            for key, path in paths.items()
        }
        ref = datasets["harvested_area"]
        if ref.crs is None:
            raise ValueError("MAPSPAM raster CRS is missing")
        if ref.count < 46:
            raise ValueError(f"MAPSPAM raster has only {ref.count} bands")
        _validate_grid(datasets, ref)

        for polygon in polygons:
            geom = polygon
            if ref.crs.to_string() != "EPSG:4326":
                from rasterio.warp import transform_geom
                geom = transform_geom("EPSG:4326", ref.crs, polygon)

            left, bottom, right, top = bounds(geom)
            raw = from_bounds(left, bottom, right, top, transform=ref.transform)

            # Expand to every pixel touched by the polygon bounding box, then
            # clip to the raster. geometry_mask applies the exact polygon.
            col_start = max(0, int(np.floor(raw.col_off)))
            row_start = max(0, int(np.floor(raw.row_off)))
            col_stop = min(ref.width, int(np.ceil(raw.col_off + raw.width)))
            row_stop = min(ref.height, int(np.ceil(raw.row_off + raw.height)))
            if col_stop <= col_start or row_stop <= row_start:
                continue

            window = Window(
                col_start,
                row_start,
                col_stop - col_start,
                row_stop - row_start,
            )
            block_height, block_width = ref.block_shapes[0]
            first_block_row = max(0, int(window.row_off // block_height))
            last_block_row = int(
                (window.row_off + window.height - 1) // block_height
            )
            first_block_col = max(0, int(window.col_off // block_width))
            last_block_col = int(
                (window.col_off + window.width - 1) // block_width
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
                    if not inside.any():
                        continue

                    # Read one band at a time to cap memory use while keeping
                    # all four COG handles open for the entire country run.
                    for band in bands:
                        arrays = {
                            key: ds.read(band, window=overlap, masked=False)
                            for key, ds in datasets.items()
                        }
                        masks = {
                            key: _valid(arrays[key], datasets[key].nodata) & inside
                            for key in datasets
                        }

                        physical_valid = (
                            masks["physical_area"] & (arrays["physical_area"] >= 0)
                        )
                        harvested_valid = (
                            masks["harvested_area"] & (arrays["harvested_area"] > 0)
                        )
                        production_valid = (
                            masks["production"] & (arrays["production"] >= 0)
                        )
                        yield_valid = (
                            masks["yield"]
                            & harvested_valid
                            & (arrays["yield"] >= 0)
                        )

                        item = totals[band]
                        item["physical_area_ha"] += float(
                            arrays["physical_area"][physical_valid].sum(dtype="float64")
                        )
                        item["harvested_area_ha"] += float(
                            arrays["harvested_area"][harvested_valid].sum(dtype="float64")
                        )
                        item["production_t"] += float(
                            arrays["production"][production_valid].sum(dtype="float64")
                        )
                        item["valid_cells"] += int(harvested_valid.sum())

                        weights = arrays["harvested_area"][yield_valid].astype("float64")
                        yields = arrays["yield"][yield_valid].astype("float64")
                        item["yield_area_weighted_sum"] += float(
                            (yields * weights).sum()
                        )
                        item["yield_weight_ha"] += float(weights.sum())

    results = []
    for band, item in totals.items():
        harvested_area = item["harvested_area_ha"]
        production = item["production_t"]
        weighted_yield = (
            item["yield_area_weighted_sum"] / item["yield_weight_ha"]
            if item["yield_weight_ha"] > 0 else None
        )
        production_yield = (
            production / harvested_area * 1000.0
            if harvested_area > 0 else None
        )
        results.append({
            "dataset_id": "mapspam-2020-v2r2",
            "reference_year": 2020,
            "technology": technology,
            "crop_band": band,
            "valid_cells": item["valid_cells"],
            "physical_area_ha": item["physical_area_ha"],
            "harvested_area_ha": harvested_area,
            "production_t": production,
            "yield_kg_ha_area_weighted": weighted_yield,
            "yield_t_ha_area_weighted": (
                weighted_yield / 1000.0 if weighted_yield is not None else None
            ),
            "yield_kg_ha_from_production_area": production_yield,
            "yield_crosscheck_abs_kg_ha": (
                abs(weighted_yield - production_yield)
                if weighted_yield is not None and production_yield is not None
                else None
            ),
            "units_note": (
                "Source units: physical/harvested area=ha, production=t, yield=kg/ha."
            ),
            "aggregation_note": (
                "Areas and production are summed; yield is harvested-area weighted."
            ),
        })
    return results
