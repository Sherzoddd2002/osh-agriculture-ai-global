# OSH Agriculture AI Global — CLI

The project supports two different modes. Choose the mode that matches the job of the computer.

## 1. Shared central server (project owner's Windows host)

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

## 2. Local isolated mode (personal sandbox)

For a standalone offline/local evaluation on a user's own computer:

```powershell
npx osh-agriculture-ai-global install
```

This creates a private SQLite database on that computer. It is not connected to the owner's central PostgreSQL and is not the shared public website.

Commands:

```powershell
npx osh-agriculture-ai-global start
npx osh-agriculture-ai-global status
npx osh-agriculture-ai-global stop
npx osh-agriculture-ai-global update
```

Requirements: Node.js 20+ and Python 3.11+ for source download and the local Python runtime; central Windows host mode also requires Python 3.12+ and access to its PostgreSQL 17.11 instance.

## Publication status

These commands become available through the public npm registry only after the repository owner publishes the package. A GitHub repository or pull request by itself does not create an npm package.
