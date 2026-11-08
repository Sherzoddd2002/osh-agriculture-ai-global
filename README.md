# Dunyo bo‘yicha hosil prognozi, NASA ma’lumotlari asosida

**OSH Agriculture AI Global** — global qishloq xo‘jaligi ma’lumotlari, hududiy tahlil va hosildorlik prognozi uchun ochiq tadqiqot platformasi.

🌍 **[Interaktiv 3D demo’ni ochish](https://sherzoddd2002.github.io/osh-agriculture-ai-global/)** · [GitHub repository](https://github.com/Sherzoddd2002/osh-agriculture-ai-global)

![OSH Agriculture AI Global public demo](docs/assets/osh-global-preview.png)

[Qisqa demo: xaritada mamlakatni tanlash → tahlil jarayoni](docs/assets/demo-walkthrough.gif)

> **Muhim:** NASA POWER platformaga tarixiy ob-havo ma’lumotlarini beradi; u hosildorlik modeli emas. Ochiq GitHub Pages demo hozircha 3D xarita va hudud tanlashni namoyish etadi. Haqiqiy hosil prognozi uchun backend API va yetarli, tekshirilgan hosildorlik tarixi kerak. Demo soxta prognoz raqamlarini ko‘rsatmaydi.

---

## Project overview

**A location-first agricultural data and yield-forecasting platform.** Users select a country and administrative area, upload historical crop observations, enrich the selected area with environmental datasets, run quality checks, and receive a clearly labelled yield estimate.

> **Status: MVP foundation.** The starter includes global administrative-boundary lookup (geoBoundaries), NASA POWER daily weather retrieval, CSV yield-data upload, SQLite for personal local installations, optional PostgreSQL/PostGIS for a shared central deployment, a database-backed background-job queue, a research forecasting endpoint, and a responsive web interface. Sentinel-2 NDVI, SMAP, and SoilGrids are explicit connector slots; they are not presented as available until their raster/data adapters and credentials are configured.

For Uzbek setup instructions, see [README_UZ.md](README_UZ.md).

## Architecture

- **Frontend:** vanilla HTML/CSS/JS + MapLibre GL JS.
- **API:** FastAPI (Python).
- **Database:** each personal local installation uses its own SQLite file. The optional shared-server/Docker deployment uses PostgreSQL; PostGIS is optional.
- **Background work:** a local worker process polls the installation's own database-backed job queue. No cloud worker is required for personal mode.
- **Environmental sources:** geoBoundaries, NASA POWER annual historical weather, and Open-Meteo current/16-day forecast are connected. NDVI, SMAP, SoilGrids remain explicit `PLANNED_CONNECTOR` sources.
- **Deployment:** GitHub source + local CLI for personal use; Docker Compose or a separately hosted central backend are optional alternatives.

## Optional: shared central Windows + PostgreSQL server

For one shared multi-user website backed by an existing PostgreSQL 17.11 host, see [docs/CENTRAL_WINDOWS_POSTGRES.md](docs/CENTRAL_WINDOWS_POSTGRES.md). The owner can install/start the central server with:

```powershell
npx osh-agriculture-ai-global server-install
npx osh-agriculture-ai-global server-status
```

This mode uses the dedicated osh_global_app role and osh_agriculture_global database on localhost:5433. The database port must not be exposed to the public internet. Publish only the web app on 127.0.0.1:8080 through a configured HTTPS tunnel. End users access the public website in a browser; they do not run the server installer.

The central host stores users' records in one PostgreSQL database with account-level ownership checks. The current Windows-host topology is a single point of failure; configure backups, monitoring, automatic startup, and security controls before unrestricted public signup.

## Recommended: one local installation per person

Each person can run the application on their own computer without Fly.io or a shared cloud database. The local CLI uses a private SQLite database and binds the web server to `127.0.0.1:8080`.

Requirements: Git, Node.js 20+, Python 3.11+, and internet access for the first install and external boundary/weather APIs. Docker and PostgreSQL are not required for this mode.

Windows PowerShell:

```powershell
git clone https://github.com/Sherzoddd2002/osh-agriculture-ai-global.git
cd osh-agriculture-ai-global
.\ops\local.ps1 install
```

Or run the CLI directly:

```powershell
node .\bin\cli.js install
```

The installer opens <http://127.0.0.1:8080>. Keep the terminal window open while the local web server is running. From the same repository folder, use `.\ops\local.ps1 start, status, stop, and update` to manage it. See [docs/LOCAL_PER_USER.md](docs/LOCAL_PER_USER.md).

Each computer has its own database and its own user data. Local instances do not synchronize with each other or with the maintainer's PostgreSQL database. The MAPSPAM rows imported into a developer's database are not included in a fresh local install; distributing those reference rows requires a separately versioned data bundle.

## Alternative: local Docker Compose stack

For developers who prefer PostgreSQL/PostGIS in Docker rather than the personal SQLite installer:

```bash
cp .env.example .env
# Replace JWT_SECRET with a long random secret.
docker compose up --build
```

Open <http://127.0.0.1:8080> and API docs at <http://127.0.0.1:8080/docs>. Compose binds the web app and optional database port to loopback only. The named database volume persists between restarts; `docker compose down -v` deletes it.

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

## GitHub source

Repository: <https://github.com/Sherzoddd2002/osh-agriculture-ai-global>

Clone the public source with `git clone https://github.com/Sherzoddd2002/osh-agriculture-ai-global.git`. Do not commit `.env`, private user datasets, raw satellite rasters, credentials, or private OSH evidence. See [README_UZ.md](README_UZ.md).

## Sources and licensing

- geoBoundaries `gbOpen`: verify and retain per-boundary license metadata and attribution.
- NASA POWER: daily point weather source; this MVP uses a representative point, not polygon-wide zonal statistics.
- Sentinel-2, SMAP, SoilGrids connectors must each declare units, source version, quality flags, temporal/spatial coverage, and licensing when implemented.

Application code is MIT; third-party data and map tiles retain their own licenses.
