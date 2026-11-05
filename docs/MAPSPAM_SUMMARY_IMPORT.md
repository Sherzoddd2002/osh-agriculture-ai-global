# MAPSPAM regional summary import

The MAPSPAM source rasters remain in the configured global-data directory.
Only verified aggregate rows are stored in PostgreSQL, in the separate
global_raster_summaries table. FAOSTAT's global_crop_statistics table is
not modified by this import.

## 1. Validate the paired outputs first

Keep the ADM1 and ADM0 CSVs from the same MAPSPAM run together. The importer
checks the source dataset/year, all 46 crop bands, per-region crop coverage,
duplicate identities, non-negative values, spatial status, and ADM1-to-ADM0
conservation. It rejects the pair before writing anything if a check fails.

Example (PowerShell):

    $Base = "E:\OSH\AgricultureAI"
    $Source = "$Base\source\osh-agriculture-ai-global-main"
    $Python = "$Base\central-server\.venv\Scripts\python.exe"
    $Results = "$Base\global-data\mapspam-2020-v2r2\results\uzb\ci-main"

    $env:OSH_AGRI_HOME = $Base
    $env:OSH_AGRI_DATA_DIR = "$Base\global-data"
    $env:DATABASE_URL = "postgresql+psycopg://osh_global_app@127.0.0.1:5433/osh_agriculture_global"
    $env:PYTHONPATH = "$Source\backend"
    & $Python -m app.import_mapspam_results --adm1-csv "$Results\.ci-mapspam-output\mapspam_2020_adm1.csv" --adm0-csv "$Results\.ci-mapspam-adm0-output\mapspam_2020_adm0.csv" --dry-run

## 2. Commit the import

After the dry run reports PASS, run the same command without --dry-run.
The command initializes only missing ORM tables, validates both files again,
and inserts or updates rows in one database transaction. Its unique key is
(dataset, source year, country, admin level, admin ID, technology, crop code),
so repeating the same import updates the existing rows rather than creating
duplicates.

The connection uses the configured DATABASE_URL. For the central Windows
installation, it should point to the dedicated osh_agriculture_global
database on 127.0.0.1:5433; never point it at the separate trading database
osh, and never expose PostgreSQL to the public internet.

## 3. Read the imported results

The public read endpoint is:

    GET /api/v1/global-raster-summaries

Useful filters include country_iso3=UZB, admin_level=ADM1,
crop_code=whea, source_year=2020, technology=all, and
dataset_id=mapspam-2020-v2r2. Pagination uses limit (1–5000) and
offset.

Examples:

- All 644 Uzbekistan regional crop rows:
  /api/v1/global-raster-summaries?country_iso3=UZB&admin_level=ADM1&source_year=2020
- Wheat by 14 regions:
  /api/v1/global-raster-summaries?country_iso3=UZB&admin_level=ADM1&crop_code=whea
- The 46 country totals:
  /api/v1/global-raster-summaries?country_iso3=UZB&admin_level=ADM0

## 4. Global multi-country run

The MAPSPAM raster is global, so it is downloaded once and reused for every
country. The resumable runner enumerates the ISO3 country catalog automatically
when `--countries` is omitted. It writes one ADM0 CSV and one ADM1 CSV, plus
separate error logs and checkpoints for each level.

Run from the Windows central installation (first run may take substantial time):

    $Base = "E:\\OSH\\AgricultureAI"
    $Source = "$Base\\source\\osh-agriculture-ai-global-main"
    $Python = "$Base\\central-server\\.venv\\Scripts\\python.exe"
    $Output = "$Base\\global-data\\mapspam-2020-v2r2\\results\\global"

    $env:OSH_AGRI_HOME = $Base
    $env:OSH_AGRI_DATA_DIR = "$Base\\global-data"
    $env:PYTHONPATH = "$Source\\backend"

    # Download and validate the four global core rasters once.
    & $Python -m app.sync_global_rasters --dataset mapspam --data-dir "$Base\\global-data"

    # No --countries argument means the full ISO3 country catalog.
    & $Python -m app.run_global_mapspam --level ADM0 --technology all --data-dir "$Base\\global-data" --output-dir $Output --resume
    & $Python -m app.run_global_mapspam --level ADM1 --technology all --data-dir "$Base\\global-data" --output-dir $Output --resume

    $Adm1 = "$Output\\mapspam_2020_adm1.csv"
    $Adm0 = "$Output\\mapspam_2020_adm0.csv"

    # First validate all countries strictly. No database writes happen here.
    & $Python -m app.import_mapspam_results --adm1-csv $Adm1 --adm0-csv $Adm0 --dry-run

    # When some countries lack boundaries or fail conservation, explicitly
    # allow a partial import. Only verified country/technology pairs are kept.
    & $Python -m app.import_mapspam_results --adm1-csv $Adm1 --adm0-csv $Adm0 --allow-partial-countries --dry-run

    # After reviewing the PARTIAL/PASS report and rejected_groups, commit the
    # validated subset in one database transaction by removing --dry-run.
    & $Python -m app.import_mapspam_results --adm1-csv $Adm1 --adm0-csv $Adm0 --allow-partial-countries

Use `--countries UZB,KAZ,TUR` for a controlled pilot instead of the complete
catalog. Keep the generated `*_errors.csv` files and completed checkpoints:
`--resume` continues unfinished countries/zones without redoing completed
work. A partial import is never implicit; the flag must be supplied explicitly,
and the validation report lists every skipped country/technology group.

## Interpretation and null handling

The stored rows remain MAPSPAM 2020 gridded estimates, not current-year
observations or field measurements. geoBoundaries ADM1 boundaries in this
run are vintage 2017. NO_RASTER_CELLS remains a separate spatial status;
missing weighted yield remains SQL NULL and is never silently converted to
zero. Physical area, harvested area and production are stored in their source
units (ha, ha and tonnes respectively). Yield is an area-weighted mean in
tonnes per hectare and must not be summed.
