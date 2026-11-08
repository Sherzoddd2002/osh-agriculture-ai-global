# OSH Agriculture AI Global — CLI

The project supports two different modes. Choose the mode that matches the job of the computer.

## Optional: shared central server (project owner's Windows host)

This is the mode for one shared website and one shared PostgreSQL database. Run it only on the Windows computer that already hosts PostgreSQL 17.11 and the database osh_agriculture_global.

After the npm package is published:

```powershell
npx osh-agriculture-ai-global server-install
```

This downloads the public source, creates a private Python virtual environment, checks the dedicated osh_global_app connection through Windows pgpass.conf, initializes the central PostgreSQL schema, and starts one FastAPI server plus one background worker.

Management commands:

```powershell
npx osh-agriculture-ai-global server-status
npx osh-agriculture-ai-global server-stop
npx osh-agriculture-ai-global server-start
npx osh-agriculture-ai-global server-update
```

Persistent central configuration, the generated JWT signing secret, Python environment, PID files, and logs are stored under the Windows user's application-data directory in OSH/AgricultureAI/central-server, not inside the replaceable source download. PostgreSQL passwords are never placed in the generated config; psycopg reads them from pgpass.conf.

The server listens on 127.0.0.1:8080. To give it a public HTTPS address, configure a Cloudflare Tunnel route to http://127.0.0.1:8080. Do not expose port 5433. See docs/CENTRAL_WINDOWS_POSTGRES.md.

End users do not run the server installer. They open the owner's published HTTPS URL, register, choose their region, and upload a crop-yield CSV when they have one. Each user's private rows are stored in the same PostgreSQL database and filtered by account ownership.

## Recommended: per-user local mode from GitHub (no npm publication required)

Every person can install a private local copy on their own computer. The CLI creates a separate SQLite database and binds the web app to `127.0.0.1:8080`. This is not a shared website; data is not synchronized between computers.

Requirements: Git, Node.js 20+, Python 3.11+, and internet access for source download and external APIs. Docker and PostgreSQL are not required.

Windows PowerShell:

```powershell
git clone https://github.com/Sherzoddd2002/osh-agriculture-ai-global.git
cd osh-agriculture-ai-global
.\ops\local.ps1 install
```

Direct CLI alternative:

```powershell
node .\bin\cli.js install
```

The installer creates its runtime, environment file, worker, and SQLite database under the current user's application-data folder, then opens the local website. Keep the terminal open while the server runs.

Management commands from the cloned repository:

```powershell
.\ops\local.ps1 start
.\ops\local.ps1 status
.\ops\local.ps1 stop
.\ops\local.ps1 update
```

On macOS/Linux, use `node ./bin/cli.js install` and the same CLI subcommands.

The local installer does not copy data from the project maintainer's PostgreSQL database. The MAPSPAM reference rows currently imported by the maintainer must be distributed separately as a versioned data bundle before they can appear in every local instance.

## Publication status

The GitHub checkout instructions above work without publishing an npm package. The shorter `npx osh-agriculture-ai-global ...` commands become available only after the repository owner publishes the package to the public npm registry.
