# Global crop raster data

OSH keeps original rasters on disk and stores only metadata and derived summaries
in PostgreSQL. The global raster directory is resolved in this order:

1. `OSH_AGRI_DATA_DIR`, when explicitly set.
2. `OSH_AGRI_HOME\global-data`, when the central installation home is set.
3. `data/global` as a development fallback.

This prevents 0.8 GB NetCDF archives and multi-GB raster collections from being
loaded into RAM or copied into every user workspace.

## Supported official sources

| Dataset | Coverage | Resolution | Variables | Role |
|---|---:|---:|---|---|
| IFPRI MAPSPAM 2020 v2r2 | 46 crops | 5 arc-minute (~9.3 km at equator) | physical area (ha), harvested area (ha), production (t), yield (kg/ha); all/irrigated/rainfed | Regional and subnational production/yield summaries |
| CROPGRIDS v1.08 | 173 crops | 0.05° (~5.6 km at equator) | physical crop area (ha), harvested area (ha), quality and source-set layers in each NetCDF | Crop footprint / crop presence prior, not yield labels |

MAPSPAM source units are **hectares**, **tonnes**, and **kg/ha**. The published
COGs have one band per crop, in the catalog crop order. Production and area are
additive. Yield is not additive: zonal yield is a harvested-area-weighted mean.
The service also computes production / harvested area as an independent
cross-check.

CROPGRIDS is an area-distribution dataset, not a production or yield dataset.
Its harvested area may exceed physical area where multiple harvest cycles occur.

## Windows install and data sync

The installer creates the Python environment at
`E:\OSH\AgricultureAI\central-server\.venv` and keeps source code at
`E:\OSH\AgricultureAI\source`. Use that Python environment and persistent
data directory:

```powershell
$env:OSH_AGRI_HOME = "E:\OSH\AgricultureAI"
$env:OSH_AGRI_DATA_DIR = "E:\OSH\AgricultureAI\global-data"

cd E:\OSH\AgricultureAI\source
$python = "E:\OSH\AgricultureAI\central-server\.venv\Scripts\python.exe"

& $python -m backend.app.sync_global_rasters --dataset mapspam
```

The default MAPSPAM sync downloads the four core `all` technology COGs
(physical area, harvested area, production and yield) plus crop-code metadata.
This is enough for 46-crop regional area/production/yield summaries. It avoids
downloading the separate irrigated and rainfed files until they are needed.

To download all 12 COG layers (four variables × three technologies):

```powershell
& $python -m backend.app.sync_global_rasters --dataset mapspam --all-technologies
```

To download selected layers only:

```powershell
& $python -m backend.app.sync_global_rasters --dataset mapspam --assets harvested_area-all production-all yield-all
```

To download CROPGRIDS v1.08 (806,855,203 bytes, approximately 807 MB):

```powershell
& $python -m backend.app.sync_global_rasters --dataset cropgrids
```

Use `--dataset both` to sync both MAPSPAM core layers and CROPGRIDS.

The downloader streams 1 MiB chunks to a temporary file on the same filesystem,
checks HTTP Content-Length, verifies the published CROPGRIDS size and MD5, and
atomically renames only after validation. MAPSPAM GeoTIFFs are opened with
Rasterio and checked for 46 bands, EPSG:4326 and valid dimensions before they
are marked as downloaded. An invalid cached COG is deleted and downloaded again.

## API

The catalog and download status are public metadata endpoints:

- `GET /api/v1/global-raster-catalog`
- `GET /api/v1/global-raster-status`

After login, submit one Polygon or MultiPolygon GeoJSON to:

`POST /api/v1/global-raster-summary/mapspam`

Example body:

```json
{
  "geojson": {
    "type": "Polygon",
    "coordinates": [[[60, 40], [61, 40], [61, 41], [60, 41], [60, 40]]]
  },
  "crop_code": "whea",
  "technology": "all",
  "location_name": "Example district",
  "admin_level": "ADM2"
}
```

The endpoint requires a bearer access token. `crop_code` must be one of the
46 MAPSPAM crop codes returned by the catalog endpoint. The API reports the
source year, raster-supported cell count, areas, production, weighted yield and
a production/area cross-check. It returns HTTP 503 when required raster assets
have not yet been synced.

## Administrative levels and scientific limits

The boundary service requests geoBoundaries ADM0–ADM5 where available. ADM3/4/5
availability varies by country; there is no universal global ADM5 boundary
layer. A missing ADM level must be reported as unavailable, not silently
represented by a larger region.

MAPSPAM's ~9.3 km grid is suitable for broad regional and subnational summaries,
not farm/field-scale truth. For very small polygons, report cell count and low
spatial support. A polygon smaller than the source grid may intersect no cell
under the default pixel-center inclusion rule.

CROPGRIDS and MAPSPAM are both reference-year 2020 spatial products. Neither is
an annual local yield panel, and CROPGRIDS does not contain production/yield
labels. Do not use them alone to claim that a crop was grown in a particular
recent year or to generate a field-level current-year yield observation.

## Model fallback policy

1. Use observed local crop yield history when it is adequate.
2. If local history is absent, use official country/crop FAOSTAT time series.
3. Use MAPSPAM as a 2020 spatial production prior and regional cross-check, not
   as invented yearly local observations.
4. Use CROPGRIDS only as crop-area / crop-presence context.
5. If local labels are absent, a country or regional model may produce a
   clearly labelled **regional proxy estimate** only when enough comparable
   observations exist. Report source years, training sample count, spatial
   level, uncertainty and fallback tier.
6. If there is insufficient evidence, return **insufficient data** rather than
   fabricate a precise ADM3–ADM5 forecast.

A 2020 raster baseline is not a global annual panel. The next stage is to
combine annual FAOSTAT/official national statistics, weather history
(NASA POWER / ERA5-Land), soils, irrigation and geospatial crop masks, then
validate held-out years and countries before promoting a regional model to
production.
