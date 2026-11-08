# Environmental connectors and small-area analysis

This document separates **catalogue availability**, **data access**, **raster processing**, and **validated model features**. A source must not be marked fully active just because its catalogue or download URL exists.

## Current connector readiness

| Source | Current state | Implemented now | Still required for usable model features |
|---|---|---|---|
| NASA POWER | Active | Daily point weather history | Polygon-wide zonal statistics; current MVP samples the saved AOI representative point |
| Open-Meteo | Active | Current conditions and up to 16-day point forecast | Forecast is not historical observation and must not be used as observed yield-season weather |
| Sentinel-2 | Catalogue available | CDSE STAC search for Sentinel-2 L2A intersecting the saved AOI, date range and cloud threshold | Authenticated/controlled asset access as required, raster download, B04/B08 alignment, SCL/CLD cloud-shadow mask, NDVI, per-pixel valid counts, seasonal zonal statistics, persistent result storage |
| NASA SMAP | Dataset available; Earthdata access required | Product metadata and source readiness declaration | Earthdata authentication, granule query/download, HDF5/NetCDF decoding, quality-flag filtering, reprojection, AOI zonal statistics, temporal aggregation |
| SoilGrids | WCS/WebDAV available; REST paused | Source endpoints and WCS integration plan | WCS capabilities/coverage selection, subset download, depth/quantile selection, raster masking, nodata/uncertainty-aware zonal statistics |

### Sentinel-2

The connected API route is:

`GET /api/v1/locations/{location_id}/sentinel2-scenes`

Query parameters: `start_date`, `end_date`, `max_cloud_percent`, and `limit`.

This route returns catalogue metadata only. It reports `catalogue_only=true` and `ndvi_status=NOT_COMPUTED`. It does **not** create an NDVI feature. For NDVI, use surface reflectance:

`NDVI = (B08 - B04) / (B08 + B04)`

Use B04 red and B08 NIR at 10 m. SCL/CLD masks are at 20 m and need a documented nearest-neighbour alignment to the 10 m grid. Exclude defective/no-data, cloud shadow, cloud probability, cirrus and snow classes according to the adopted processing policy. Retain the source scene IDs, processing version, valid-pixel count, mask coverage and temporal aggregation window for every statistic.

CDSE STAC catalogue is available at `https://stac.dataspace.copernicus.eu/v1/`; collection is `sentinel-2-l2a`. The current UI can search scenes for a saved polygon.

### NASA SMAP

Recommended product for a first soil-moisture connector: `SPL3SMP_E`, Version 6, daily Enhanced L3 radiometer, global 9 km EASE-Grid. A free NASA Earthdata Login is needed to download protected data. Preserve retrieval-quality and surface flags. A 9 km signal is regional context, not a small-field measurement.

Do not interpolate SMAP to 10 m and describe it as 10 m information. If combined with Sentinel-2, the modelling table must keep each feature's true native resolution and valid observation count.

### SoilGrids

ISRIC currently documents that SoilGrids REST API is paused. WCS is the preferred method for requesting a geographic subset; WebDAV VRT files are another option. SoilGrids predictions are 250 m modelled soil properties with uncertainty information, not laboratory values. A small field may contain very few or no independent 250 m pixels.

Use WCS in this order:
1. `GetCapabilities` to discover available property coverages.
2. `DescribeCoverage` to confirm depth, quantile, CRS and raster metadata.
3. `GetCoverage` to request only the AOI bounding box.
4. Mask the returned raster by the exact AOI polygon and calculate valid-pixel statistics.
5. Preserve the 90% prediction interval/uncertainty when available.

## Small fields: administrative boundaries are not field boundaries

The geoBoundaries ADM0–ADM5 levels are administrative units. They do not represent an individual farm or field. The full app now includes **Maydon chizish** in the map toolbar:

1. Open the app's Global Map view.
2. Select the country ISO-3 code and press **Chegaralarni yuklash** for administrative areas, or press **Maydon chizish**.
3. Click at least three vertices around the field, in order; press **Tugatish**.
4. Sign in and save the selected AOI.

A custom polygon is saved as `CUSTOM`; it is not assigned a fabricated ADM2/ADM3 ID. MAPSPAM summaries only appear for precomputed administrative IDs that were imported and reconciled. A custom AOI must instead be sampled against a suitable raster source.

For small parcels, Sentinel-2 at 10 m is the most relevant of these three sources for vegetation-condition analysis. MAPSPAM is approximately 9.3 km at the equator, SMAP is approximately 9 km, and SoilGrids is 250 m. Those coarser grids cannot provide field-scale values just because a user draws a smaller polygon.

## Why the AI forecast may not run

There are two distinct modelling routes:

1. **Public FAOSTAT trend baseline:** uses a country's available annual national yield history or a labelled global proxy. It is a national/global historical trend scenario, not a district or field forecast.
2. **Location/dataset model:** upload an authentic yield CSV for the saved AOI. The current model pipeline requires at least eight yield observations, at least eight weather-aligned rows, and at least two usable environmental features. It compares Linear Regression, Ridge, ElasticNet, Random Forest, Extra Trees and HistGradientBoosting against Persistence using expanding chronological validation.

The dataset-specific model does not run just because an AOI is saved. An AOI without observed yield labels can produce a climate report, but not a supervised yield model. No placeholder/synthetic yield labels are created.

## Deployment requirements

GitHub Pages serves the static `docs/` dashboard only. It cannot run FastAPI routes, access PostgreSQL, or execute background jobs.

The actual application requires:
- FastAPI web service;
- PostgreSQL (or a local SQLite instance for one-user local mode);
- the background worker process;
- correct `DATABASE_URL`, `JWT_SECRET`, CORS origin and external-source settings.

The health endpoint exposes `background_worker.status`. A running API with an offline worker can accept a job but cannot complete its processing. Publish the API through an HTTPS reverse proxy/tunnel; never expose PostgreSQL port 5433 directly.

## Sources

- [Copernicus Data Space STAC API](https://documentation.dataspace.copernicus.eu/APIs/STAC.html)
- [Sentinel-2 L2A bands and resolutions](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S2L2A.html)
- [NASA NSIDC SMAP SPL3SMP_E Version 6](https://nsidc.org/data/spl3smp_e/versions/6)
- [SMAP retrieval-quality and surface flags](https://nsidc.org/data/user-resources/help-center/how-do-i-interpret-surface-and-quality-flag-information-level-2-and-3-passive-soil-moisture-products)
- [SoilGrids data access status](https://docs.isric.org/globaldata/soilgrids/)
- [SoilGrids WCS subset access](https://docs.isric.org/globaldata/soilgrids/wcs.html)
