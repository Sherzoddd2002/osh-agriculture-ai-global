# Fly.io deployment — one web Machine + external PostgreSQL

This low-cost topology uses **one Fly Machine** for FastAPI and its background worker, plus an external PostgreSQL provider. It deliberately does not provision Fly Managed Postgres or a second Fly worker Machine.

## Database

Use a persistent PostgreSQL database with TLS. Neon Free currently includes 1 GB of Postgres storage, 100 CU-hours per project per month, and 5 GB of public network transfer. The free compute scales to zero after five minutes of inactivity, so the first query after idle can be slower. Keep an eye on storage and transfer limits; the full ADM2/ADM3 dataset may exceed the free 1 GB database allowance.

Do not put database credentials in Git. Set the connection URL as a Fly secret:

```bash
fly secrets set DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require' -a osh-agriculture-ai-global
fly secrets set JWT_SECRET='A_RANDOM_SECRET_AT_LEAST_32_CHARACTERS' -a osh-agriculture-ai-global
```

## One-Machine application

The Fly configuration defines only the `web` process group. `RUN_WORKER_IN_WEB=true` starts the queue worker as a daemon thread inside the FastAPI process, avoiding a second Machine. Do not add Uvicorn `--workers > 1` while using this mode; each process would start another queue worker.

The Fly Machine is configured at shared CPU, 512 MB RAM. This is a small starting size, not a capacity guarantee. Monitor memory and increase to 1 GB if the Machine is OOM-killed or the app becomes unstable.

```bash
fly deploy -a osh-agriculture-ai-global
fly scale count 1 --process-group web -a osh-agriculture-ai-global
fly status -a osh-agriculture-ai-global
```

The web Machine stays running (`auto_stop_machines = "off"`) so background jobs continue when no requests are in flight. Fly compute is billed while running; this is not a perpetual free tier. Check the account's billing/trial status and current regional pricing before deploying.

## Verify

```bash
fly checks list -a osh-agriculture-ai-global
```

Then open:

- `https://osh-agriculture-ai-global.fly.dev/`
- `https://osh-agriculture-ai-global.fly.dev/api/v1/health`
- `https://osh-agriculture-ai-global.fly.dev/docs`

The health endpoint must return `ok: true` and `database: connected`.

## Data migration

Keep the local PostgreSQL backup. Migrate data into the external cloud database before announcing the public site. The local Windows PostgreSQL server is not reachable from Fly.io unless a secured migration path is explicitly configured. Never expose local port 5433 to the public internet.

## Availability and cost

- One shared-cpu-1x Machine with 512 MB RAM is the lowest practical starting point for this Python image; actual memory use must be monitored.
- Neon Free storage/compute/network quotas are limits, not an uptime SLA.
- A single Fly Machine is a single point of failure. This is a budget-first MVP topology, not high availability.
- Machine compute, egress, storage, and external database usage can incur charges. Review the Fly and Neon dashboards and set billing alerts.

## Before production launch

- Add Alembic migrations; the MVP bootstrap uses `create_all()` and raw PostGIS column creation.
- Add rate limiting, email verification, password reset, abuse controls, file scanning, and privacy/terms pages.
- Add object storage for raw uploads and raster outputs.
- Add global training data review/approval, dataset consent withdrawal, reproducible model registry, country-held-out tests, and future-year tests.
