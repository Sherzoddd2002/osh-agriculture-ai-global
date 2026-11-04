# Global crop data (FAOSTAT baseline)

The central PostgreSQL service stores country-level official crop statistics imported from
FAOSTAT's "Production: Crops and livestock products" (QCL) normalized bulk release.

The initial curated catalog contains wheat, maize (including FAOSTAT's "Maize (corn)"),
rice/paddy rice, barley, soybean/soya beans, cotton lint, potatoes and sorghum. The importer
reads the CSV in 200,000-row chunks, normalizes the source units (1000 ha, 1000 t, hg/ha),
keeps FAOSTAT element flags, maps UN M49 area codes to ISO-3, and skips regional/world
aggregate rows to avoid double counting. It loads into a staging list first; replacement
of the live FAOSTAT_QCL snapshot occurs in one database transaction. A failed or empty
import does not delete the previous completed snapshot.

After updating the central server, run from the source backend folder:

```powershell
$home = "E:\OSH\AgricultureAI"
Set-Location "$home\source\backend"
& "$home\central-server\.venv\Scripts\python.exe" -m app.sync_global_data
```

Authenticated endpoints:
- `GET /api/v1/global-crops` — loaded crop coverage and year ranges.
- `POST /api/v1/global-predictions/yield` with `country_iso3`, `crop_code`, `target_year`.

Prediction hierarchy:
1. At least 8 country-year observations: national trend model.
2. Otherwise: global area-weighted crop trend, adjusted by a country/global ratio only when
   at least 3 matching years exist.
3. If the global series is too short: return HTTP 422; do not fabricate a forecast.

The baseline uses expanding-window temporal validation and compares MAE with a persistence
baseline. Its uncertainty band is approximate. It is a national/global proxy, never a district
or field measurement. Raster zonal statistics (MAPSPAM/CROPGRIDS), climate and soil features
are not yet part of this baseline and must be added and validated before claiming ADM3–ADM5
yield prediction accuracy.

The source is FAOSTAT QCL. FAO data released under CC BY 4.0 requires attribution to FAO.
Boundary lookup tries geoBoundaries gbOpen first and gbHumanitarian second. Availability and
administrative meaning vary by country. A requested ADM level is returned only when the
provider supplies a non-empty FeatureCollection; missing levels are not invented. Review
each boundary provider's returned licence and attribution metadata before redistribution.
