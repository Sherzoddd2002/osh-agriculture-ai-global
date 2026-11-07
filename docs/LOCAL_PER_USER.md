# Per-user local installation

This mode is for people who want to run OSH Agriculture AI on their own computer. It does not require Fly.io, a hosted PostgreSQL database, or Docker.

## What each person gets

- A local web application at `http://127.0.0.1:8080`.
- A separate SQLite database on that computer.
- A local background worker for queued climate and analysis jobs.
- Private accounts and records within that local installation.
- No automatic sharing or synchronization with other computers.

The local CLI binds to loopback (`127.0.0.1`), so the website is not exposed to the LAN or public internet by default.

## Requirements

- Git.
- Node.js 20 or newer.
- Python 3.11 or newer.
- Internet access during first installation to download the source and Python packages.
- Internet access for live geoBoundaries, NASA POWER, Open-Meteo, and map tile requests.

Docker and PostgreSQL are not needed for the personal local mode.

## Windows installation from GitHub

Open PowerShell:

```powershell
git clone https://github.com/Sherzoddd2002/osh-agriculture-ai-global.git
cd osh-agriculture-ai-global
.\ops\local.ps1 install
```

The same command without the PowerShell helper is:

```powershell
node .\bin\cli.js install
```

The installer downloads the current `main` source from GitHub, creates a private Python virtual environment, installs dependencies, creates the SQLite schema, starts the worker and web server, and opens the browser.

The web process runs in the foreground. Keep the PowerShell window open while using the application.

## Start, status, stop, and update

Run these commands from the cloned repository:

```powershell
.\ops\local.ps1 start
.\ops\local.ps1 status
.\ops\local.ps1 stop
.\ops\local.ps1 update
```

The direct CLI equivalents are `node .\bin\cli.js start|status|stop|update`.

- `start` starts the worker and web server.
- `status` reports whether the local web server and worker are running.
- `stop` stops only the OSH Agriculture web and worker processes.
- `update` downloads the latest `main` source, updates Python packages/schema, and keeps the existing local SQLite file and generated secret.

## Where local data lives

The CLI stores data outside the cloned source folder so source updates do not delete user data.

- Windows: `%LOCALAPPDATA%\OSH\AgricultureAI\data\agriculture.sqlite3`
- macOS: `~/Library/Application Support/OSH/AgricultureAI/data/agriculture.sqlite3`
- Linux: `~/.local/share/osh-agriculture-ai-global/data/agriculture.sqlite3`

The generated runtime configuration is stored under the same application-data folder. Do not commit that folder, the SQLite database, or user-uploaded files to GitHub.

Stop the app before manually copying the SQLite file for backup. Do not delete the application-data folder during an ordinary source update.

## Local means separate data

Every computer has its own database. A dataset uploaded on one computer does not appear on another person's computer. Accounts on the same local installation are separated by the application's owner checks, but all that installation's records remain on that computer.

If all users need one shared dataset, shared accounts, and synchronized results, use a central hosted backend and database instead. A `localhost` installation is not a public multi-user website.

## MAPSPAM reference-data limitation

The MAPSPAM ADM0/ADM1 rows imported into the maintainer's local PostgreSQL database are not automatically included in a new SQLite installation. A fresh local install creates the required table but does not populate those rows. The MAPSPAM reference dataset must be packaged as a separately versioned downloadable data bundle, with source/license attribution and an import step, before every local installation can display those reference summaries.

The local app can still use its connected boundary and weather APIs and users can upload their own crop-yield CSV files.

## Alternative Docker Compose mode

The repository also includes a local PostgreSQL/PostGIS Docker Compose stack for developers who want PostgreSQL instead of the personal SQLite CLI. It is still local to one computer; it does not synchronize data with other installs. The Compose ports are bound to loopback only.
