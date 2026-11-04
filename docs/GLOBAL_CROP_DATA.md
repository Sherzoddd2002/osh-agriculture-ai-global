# Global crop data (FAOSTAT baseline)

The central PostgreSQL service can store country-level official crop observations from FAOSTAT's
"Production: Crops and livestock products" bulk release. This first connector imports a curated
starter set: wheat, maize, rice, barley, soybean, cotton, potato and sorghum.

Run the importer from the installed central runtime after updating the application:

```powershell
$home = "E:\OSH\AgricultureAI\central-server"
& "$home\.venv\Scripts\python.exe" -m app.sync_global_data
```

The importer downloads the official FAOSTAT normalized ZIP, maps M49 country codes to ISO-3,
normalizes area/production/yield units, and replaces the FAOSTAT_QCL snapshot transactionally.
The raw source archive is not stored in PostgreSQL.

Authenticated endpoints:
- `GET /api/v1/global-crops` — loaded crop coverage and year ranges.
- `POST /api/v1/global-predictions/yield` with `country_iso3`, `crop_code`, `target_year`.

Prediction hierarchy:
1. At least 8 country-year observations: national trend model.
2. Otherwise: global area-weighted crop trend, adjusted by a country/global ratio only when
   at least 3 matching years exist.
3. If the global series is too short: return HTTP 422; do not fabricate a forecast.

The baseline uses an expanding-window time validation and compares MAE with persistence.
Its uncertainty band is approximate. It is a national/global proxy, never a district or field
measurement. Raster zonal statistics (MAPSPAM/CROPGRIDS), climate and soil features are not
yet part of this baseline and must be added and validated before claiming ADM3–ADM5 yield
prediction accuracy.

Administrative boundary lookup tries geoBoundaries gbOpen first and gbHumanitarian second.
Availability and administrative meaning vary by country. A requested ADM level is returned
only when the provider supplies a non-empty FeatureCollection; missing levels are not invented.
Always review provider metadata and licensing before redistributing downloaded boundary data.
