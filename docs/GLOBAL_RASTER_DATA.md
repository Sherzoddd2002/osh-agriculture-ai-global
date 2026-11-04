# Global crop raster data

OSH keeps source rasters on disk and stores only metadata and derived summaries in
PostgreSQL. This prevents 0.8 GB NetCDF archives and multi-GB raster collections
from being loaded into RAM or copied into every user workspace.

## Supported official sources

| Dataset | Coverage | Resolution | Variables | Role |
|---|---:|---:|---|---|
| IFPRI MAPSPAM 2020 v2r2 | 46 crops | 5 arc-minute (~9 km at equator) | physical area, harvested area, production, yield; all/irrigated/rainfed | Regional and subnational production/yield summaries |
| CROPGRIDS v1.08 | 173 crops | 5 arc-minute (~5.6 km at equator) | physical area, harvested area | Crop footprint / crop presence prior, not yield labels |

MAPSPAM source units are thousand hectares, thousand tonnes and kg/ha.
Yield is not additive: zonal yield is harvested-area weighted. Production and
area are additive. A production/harvested-area yield is also returned as a
cross-check.

## Install and sync

Set a persistent data directory outside the Git checkout. On Windows:

```powershell
$env:OSH_AGRI_DATA_DIR = "E:\OSH\AgricultureAI\global-data"
python -m backend.app.sync_global_rasters --dataset mapspam
```

By default the MAPSPAM command downloads the 12 COG assets plus crop-code metadata.
Select only the required asset IDs to reduce disk usage, for example:

```powershell
python -m backend.app.sync_global_rasters --dataset mapspam --assets physical_area-all harvested_area-all production-all yield-all
```

To download the CROPGRIDS archive (about 807 MB):

```powershell
python -m backend.app.sync_global_rasters --dataset cropgrids
```

The downloader streams 1 MiB chunks to a temporary file, verifies the published
CROPGRIDS size and MD5, then atomically renames it. Interrupted downloads never
replace a previously valid file. MAPSPAM assets are cached after download; their
COG internal structure should be checked with GDAL/rasterio before production use.

## Administrative levels and scientific limits

The boundary service requests geoBoundaries ADM0–ADM5 where available. ADM3/4/5
availability varies by country; there is no universal global ADM5 boundary layer.
A missing ADM level must be reported as unavailable, not silently represented
by a larger region. MAPSPAM's ~9 km grid is suitable for broad regional
summaries, not farm/field-level truth. For very small polygons, disclose pixel
count and low spatial support.

CROPGRIDS is a 2020 crop-area distribution product, not a time series and not
yield or production ground truth. Do not use it alone to claim that a crop was
grown in a particular recent year.

## Model fallback policy

1. Use observed local crop yield history when it is adequate.
2. If local history is absent, use official country/crop FAOSTAT time series.
3. Use MAPSPAM as a 2020 spatial prior and regional cross-check, not as invented
   yearly local observations.
4. Use CROPGRIDS only as crop-area / crop-presence context.
5. If local labels are absent, a country or regional model may produce a
   clearly labelled **regional proxy estimate** only when there are enough
   comparable observations. Report source years, training sample count,
   spatial level, uncertainty and fallback tier.
6. If there is insufficient evidence, return **insufficient data** rather than
   fabricate a precise ADM3–ADM5 forecast.

A 2020 raster baseline is not a global annual panel. The next stage is to
combine annual FAOSTAT/official national statistics, weather history (NASA
POWER / ERA5-Land), and geospatial crop masks, then validate held-out years and
countries before promoting a regional model to production.
