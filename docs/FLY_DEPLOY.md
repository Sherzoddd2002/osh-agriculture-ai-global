# Fly.io deployment checklist

1. Create a Fly.io app. Choose a primary region near the first expected users.
2. Create a separate Fly Managed Postgres cluster and enable PostGIS. Connect it using the cluster's private connection URI.
3. Set secrets:

```bash
fly secrets set DATABASE_URL='postgresql+psycopg://USER:PASSWORD@HOST:5432/DB?sslmode=require'
fly secrets set JWT_SECRET='USE_A_LONG_RANDOM_SECRET_AT_LEAST_32_CHARACTERS'
fly secrets set APP_ENV=production
```

4. Set the Fly app name in fly.toml to the deployed app name. The current repository configuration uses osh-agriculture-ai-global and the public API health URL is https://osh-agriculture-ai-global.fly.dev/api/v1/health.

5. For automatic deploys from GitHub, create a Fly deploy token and store it as a GitHub Actions repository secret named FLY_API_TOKEN. Do not commit the token or paste it into source files. Fly's GitHub Actions workflow in .github/workflows/fly-deploy.yml skips safely when the secret is absent; once the secret exists, pushes affecting backend/frontend/deployment files deploy the web service and worker.

   Fly documents deploy-token creation and the GitHub Actions secret flow here:
   https://fly.io/docs/launch/continuous-deployment-with-github-actions/

6. Deploy the Docker image. The `release_command` runs the MVP schema bootstrap before Machines receive traffic:

```bash
fly deploy
```

7. Ensure one web Machine and one worker Machine exist:

```bash
fly scale count 1 --process-group web
fly scale count 1 --process-group worker
```

8. Check `https://YOUR-APP.fly.dev/api/v1/health` and `/docs`. Create a test account, select a polygon, upload a small CSV, run environmental enrichment, inspect coverage, and only then request a prediction.

## Availability and cost

`auto_stop_machines = "off"` with `auto_start_machines = false` keeps provisioned web Machines from automatically sleeping. It does not guarantee zero downtime. For stronger availability, deploy multiple web Machines, configure health checks/monitoring/alerts, use managed database backups, and rehearse restore procedures. The worker should have a separate Machine and should be monitored as well.

Fly Machines, managed Postgres, storage, network egress, and external raster/data services can incur charges. Review current regional availability and pricing in the Fly dashboard before provisioning. Start small and configure spending alerts.

## Before production launch

- Add Alembic migrations; the MVP bootstrap uses `create_all()` and raw PostGIS column creation.
- Add rate limiting, email verification, password reset, abuse controls, file scanning, and privacy/terms pages.
- Add object storage for raw uploads and raster outputs, rather than keeping large files on a Machine root filesystem.
- Add NDVI, SMAP, and SoilGrids raster connectors with quality flags and source/license metadata.
- Add global training data review/approval, dataset consent withdrawal, reproducible model registry, country-held-out tests, and future-year tests.
