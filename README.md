# OSH Agriculture AI — Global

**A location-first agricultural data and yield-forecasting platform.** Users select a country and administrative area, upload historical crop observations, enrich the selected area with environmental datasets, run quality checks, and receive a clearly labelled yield estimate.

> **Status: MVP foundation.** The current starter includes global administrative-boundary lookup (geoBoundaries), NASA POWER daily weather retrieval, CSV yield-data upload, PostgreSQL/PostGIS persistence, a database-backed background-job queue, a first local-model research endpoint, and a responsive web interface. Sentinel-2 NDVI, SMAP, and SoilGrids are represented as explicit connector slots; they are not silently fabricated or marked as available until their raster/data adapters and credentials are configured.

For Uzbek setup instructions, see [README_UZ.md](README_UZ.md).

## Architecture

- **Frontend:** vanilla HTML/CSS/JS + MapLibre GL JS.
- **API:** FastAPI (Python).
- **Database:** PostgreSQL + PostGIS (SQLAlchemy; geometry is stored in a PostGIS `geometry` column and GeoJSON metadata in JSONB).
- **Background work:** a dedicated worker polls a PostgreSQL job queue using `FOR UPDATE SKIP LOCKED`.
- **Environmental sources:** geoBoundaries, NASA POWER annual historical weather, and Open-Meteo current/16-day forecast are connected. NDVI, SMAP, SoilGrids remain explicit `PLANNED_CONNECTOR` sources.
- **Deployment:** Docker and Fly.io process groups (`web` + `worker`); a separate managed PostGIS-compatible PostgreSQL cluster.

## Local one-command installer

After the npm package is published by the repository owner:

```bash
npx osh-agriculture-ai-global install
```

The local CLI stores each installation's data in its own SQLite database. Users do not share data or a central global training pool through this local mode. Shared multi-user operation requires a separately hosted backend and central database.

## Quick start

```bash
cp .env.example .env
# Replace JWT_SECRET with a long random secret.
docker compose up --build
```

Open <http://localhost:8080> and API docs at <http://localhost:8080/docs>.

## Dataset format

```csv
year,yield_t_ha,area_ha,production_t
2015,4.12,12000,49440
2016,4.25,12100,51425
2017,3.98,11900,47362
```

- `yield_t_ha` is tonnes per hectare.
- `area_ha` and `production_t` are optional.
- Record whether area means sown or harvested area.
- One row per crop-year per location is accepted by this MVP.

## Prediction governance

The model endpoint is a local research scenario, not a validated global crop model. It uses expanding-window chronological validation and a Persistence benchmark. It refuses to predict if fewer than eight aligned observations/features exist. Future-season weather is unknown, so a future prediction uses a recent five-year observed seasonal weather normal and is explicitly labelled `CLIMATOLOGY_SCENARIO`.

Generated yields are never re-labelled as observed values. A global training opt-in is stored as consent only; a later review must check provenance, license, units, time coverage, duplicates, and quality before the dataset enters a shared training pool.

## Fly.io

Review [docs/FLY_DEPLOY.md](docs/FLY_DEPLOY.md) before deployment. The web process has autostop disabled, and the worker is separate. This keeps the app from sleeping due to inactivity but does not guarantee zero downtime. Machines, managed Postgres, storage, data-source traffic, and egress can incur charges.

## GitHub

Create a new empty public repository named `osh-agriculture-ai-global`, then push this project. Do not upload `.env`, private user datasets, raw satellite rasters, credentials, or private OSH evidence. See [README_UZ.md](README_UZ.md).

## Sources and licensing

- geoBoundaries `gbOpen`: verify and retain per-boundary license metadata and attribution.
- NASA POWER: daily point weather source; this MVP uses a representative point, not polygon-wide zonal statistics.
- Sentinel-2, SMAP, SoilGrids connectors must each declare units, source version, quality flags, temporal/spatial coverage, and licensing when implemented.

Application code is MIT; third-party data and map tiles retain their own licenses.
