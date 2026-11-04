# Central Windows server — existing PostgreSQL 17.11

This deployment mode runs one shared FastAPI API + background worker on the owner's Windows PC. All registered users write to the same PostgreSQL database, osh_agriculture_global, while row-level owner checks keep each account's locations, datasets, jobs, and reports private.

## Topology

- Browser users: HTTPS only.
- Cloudflare Tunnel: public hostname -> http://127.0.0.1:8080.
- FastAPI and the worker: run on the Windows host.
- PostgreSQL 17.11: 127.0.0.1:5433, database osh_agriculture_global, role osh_global_app.
- Never publish PostgreSQL port 5433 or the PostgreSQL service to the internet.
- osh remains the separate Binance OSH database; it is not used by this application.

## Prerequisites on the Windows host

1. PostgreSQL 17.11 Windows service is running on port 5433.
2. osh_agriculture_global exists and is owned by osh_global_app.
3. The Windows user's %APPDATA%\postgresql\pgpass.conf has this exact mapping (password is entered locally, never committed):

   127.0.0.1:5433:osh_agriculture_global:osh_global_app:<application-role-password>

4. Python 3.12 is installed and requirements.txt dependencies can be installed.
5. The repository is checked out on the host.

The application uses DATABASE_URL=postgresql+psycopg://osh_global_app@127.0.0.1:5433/osh_agriculture_global; psycopg obtains the password from pgpass.conf. Do not put a database password in .env.central.

## Start / check / stop

Run PowerShell from the repository root:

```powershell
.\ops\start-central.ps1
.\ops\status-central.ps1
```

The start script creates .env.central on first run with a random JWT signing secret, checks that the dedicated PostgreSQL role can connect, installs requirements, initializes the schema, and starts one worker plus one web process. The .env.central file, PID files, and logs are ignored by Git.

Stop only the application processes:

```powershell
.\ops\stop-central.ps1
```

This does not stop PostgreSQL or modify the osh database. Log files are under .osh-central\logs.

## Publish HTTPS using Cloudflare Tunnel

### Temporary test URL

Install cloudflared, start the central app, then run this in a second PowerShell window:

```powershell
cloudflared tunnel --url http://127.0.0.1:8080
```

Cloudflare prints a temporary https://....trycloudflare.com URL. Anyone who has that URL can reach the web application. The URL changes on each run and only works while cloudflared and the host are online. Quick Tunnels are for testing, not production.

### Stable hostname

For a lasting public URL, use a domain added to Cloudflare:

1. Cloudflare Dashboard → Networking → Tunnels → Create Tunnel.
2. Add a Published Application route, for example agri.example.com → http://127.0.0.1:8080.
3. Install cloudflared on the Windows host and register the tunnel as a Windows service using the tunnel token from the dashboard (run PowerShell/CMD as Administrator):

   ```powershell
   cloudflared.exe service install <TUNNEL_TOKEN>
   ```

4. Confirm the tunnel and hostname work, then make sure the Windows host, PostgreSQL service, application processes, and tunnel start automatically after reboot.

Do not paste the tunnel token into GitHub, chat, or source files.

## Multi-user data and model policy

- All accounts share one PostgreSQL server and database.
- Every user's Location, Dataset, AnalysisJob, and climate jobs are owner-scoped by the API. The tests/test_multi_user_isolation.py test checks that another user cannot list or read a private location/job or attach a dataset to another user's location.
- The worker processes jobs from the shared queue. It persists environment features and job outputs centrally.
- Local dataset forecasts are trained/evaluated on the uploading user's own observed dataset. Upload consent alone does not automatically add it to a shared global model. A separate data-quality/licensing/consent review and model-governance pipeline is required before pooling datasets from different users.
- The public users' data are in your central database, so schedule encrypted backups and periodically test restores.

## Before allowing unrestricted public signups

This is a single Windows host and one worker: it has no high availability and will be offline if the PC, power, or internet is unavailable. Use UPS, automatic Windows restart, monitored process startup, backups, and resource limits.

Before broad public launch, add or verify: email verification, password reset, login/register rate limits, CAPTCHA or bot controls, upload content scanning, privacy/terms pages, a retention/delete-account flow, observability, backup/restore procedures, and database migrations (Alembic). Set CORS_ORIGINS to the exact public website origin rather than * after the domain is known.

The API binds to 127.0.0.1:8080; PostgreSQL remains bound to the local network interface and is not a public endpoint. Cloudflare Tunnel should publish only the HTTP application.
