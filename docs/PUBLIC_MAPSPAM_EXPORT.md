# Public global MAPSPAM package export

This procedure publishes only the licensed MAPSPAM 2020 v2r2 aggregate summaries that are already present in the maintainer's local PostgreSQL reference archive. It does not publish FAOSTAT rows, user uploads, credentials, or raw raster pixels.

## Preconditions

- The PostgreSQL 17.11 service is running locally on `127.0.0.1:5433`.
- The database is `osh_agriculture_global`.
- The read-only export connection uses the existing `osh_global_app` role and local PostgreSQL `pgpass.conf`.
- Python has the repository requirements installed. The helper reuses `%LOCALAPPDATA%\OSH\AgricultureAI-Central\.venv` when it exists, or a project `.venv`, or Python on PATH.

Do not put passwords, API keys, JWT secrets, or connection credentials into repository files or chat.

## Run on Windows

Open PowerShell in the repository clone and execute the two commands separately:

```powershell
cd E:\osh-agriculture-ai-global-deploy
.\ops\export-public-mapspam.ps1
```

An optional small test export can target a few ISO-3 countries first:

```powershell
.\ops\export-public-mapspam.ps1 -Countries UZB,KAZ,TUR
```

The helper sets the documented local connection string without a password, then runs the exporter and package verifier. The exporter runs SELECT queries against `global_raster_summaries`; it does not modify the database.

## Generated files

The exporter creates:

- `docs/data/mapspam/global/manifest.json`
- One `<ISO3>.json.gz` package for each country present in the database.
- Each package contains separate ADM0 country, ADM1 province/state, and ADM2 district summaries where those rows exist.

The verifier checks the source year, country identity, MAPSPAM licence, all 46 crop entries for each area, summary counts, physical/harvested area, production, valid raster cells, and the `NO_RASTER_CELLS` rule (`yield_t_ha` must remain NULL, not zero).

## Review before publishing

Review the manifest, package count and compressed size. Confirm that only `docs/data/mapspam/global/` is being staged:

```powershell
git status --short
git add docs/data/mapspam/global
git status --short
```

The global packages are public once committed to the public repository. Do not add a `.env`, database dump, FAOSTAT extracts, user CSV, password, or raw raster files.

After reviewing the generated files, commit and push them to the dashboard PR branch:

```powershell
git commit -m "Publish verified global MAPSPAM 2020 aggregates"
git push origin global-dashboard-ux-v1
```

After merge, GitHub Pages publishes the static packages. The browser fetches only the selected country package; no Fly service, public PostgreSQL, or runtime database connection is introduced.

## Interpretation

MAPSPAM 2020 is a single 2020 spatial reference, approximately 5 arc-minute (~9.3 km at the equator), for 46 crops. It supports historical spatial context and comparisons, not a current-season measurement, field-level truth, or future yield prediction. ADM0, ADM1 and ADM2 are separate hierarchical levels and must not be added together. Retain IFPRI attribution and CC BY-SA 4.0 licence information.
