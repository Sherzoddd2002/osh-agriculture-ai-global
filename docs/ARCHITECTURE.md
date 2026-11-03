# Architecture and data lineage

## Request flow

`Browser -> FastAPI -> PostGIS` saves the user's selected polygon and metadata. `CSV upload -> validation -> datasets/yield_observations`. A row in `analysis_jobs` starts the background worker. The worker fetches NASA POWER daily data at the polygon's representative point, aggregates it with the declared crop-year window, and writes feature rows to `environment_features`. The prediction API joins only observed yield targets to available environmental features, performs expanding chronological validation, compares model MAE with Persistence, and returns a labelled scenario.

## Why the queue lives in PostgreSQL for the MVP

It avoids adding Redis before we need it. Each worker claims one queued job with `FOR UPDATE SKIP LOCKED`, changes its state to RUNNING, commits, and processes it. Web requests never wait for long data downloads. If job volume grows, move this interface to Celery/Redis or a managed queue while keeping the job table as the audit record.

## Global model policy

The `global_consent` field is only a recorded opt-in. It does not automatically make a dataset trusted or train the shared model. A later ingestion-review service must check license, source, units, crop/season definition, geometry, duplicate years, outliers, and observed-vs-imputed status. Global training should use only accepted OBSERVED targets. A local user forecast must not leak into the shared training pool as a real observation.

## Planned environmental adapters

- Sentinel-2 NDVI: STAC search by geometry/time, cloud and scene classification masks, scale factors, zonal statistics, pixel support counts.
- SMAP: product/version-specific data access, quality flags, units, temporal aggregation to crop-year; product depth semantics must be clear.
- SoilGrids: soil-property raster sampling/zonal summaries by depth, retaining nominal resolution and uncertainty metadata.

Each adapter must report `AVAILABLE`, `PARTIAL`, `NO_DATA`, `NOT_CONFIGURED`, or `FAILED`, with a source version and retrieval timestamp. Never fill missing values with zero by default.
