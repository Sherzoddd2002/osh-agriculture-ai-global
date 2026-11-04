# OSH Agriculture AI Global — CLI Installer

Install the local edition from the public GitHub repository:

```bash
npx osh-agriculture-ai-global install
```

Requirements: Node.js 20+ and Python 3.11+. The installer downloads the public `main` branch, creates an isolated Python virtual environment, installs requirements, configures a private SQLite database, initializes tables, starts the background worker, and opens http://127.0.0.1:8080.

Commands:

```bash
npx osh-agriculture-ai-global start
npx osh-agriculture-ai-global status
npx osh-agriculture-ai-global stop
npx osh-agriculture-ai-global update
```

The default installation is stored outside the current directory under the user's application-data folder. Override it with the `OSH_AGRI_HOME` environment variable. The database, .env secrets and logs are kept separately from the replaceable source tree, so updates preserve local data. Stop the foreground web server with Ctrl+C in its terminal.

The local edition uses SQLite and Shapely geometry validation; PostGIS is optional for PostgreSQL deployments. Every local install has its own database. This installer does not publish a shared hosted website.

The npm package must be published by the repository owner before the `npx` command becomes available from the public npm registry.
