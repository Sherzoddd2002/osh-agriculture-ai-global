"""Stream FAOSTAT crop statistics into the central PostgreSQL database.

Run from the backend directory:
    python -m app.sync_global_data --csv "E:\\OSH\\AgricultureAI\\global-data\\faostat\\raw\\Production_Crops_Livestock_E_All_Data_(Normalized).csv"

Only FAOSTAT items with harvested-area observations are imported as crops.
All crop items are retained with a stable FAO item-code identifier when no
well-known alias exists. Regional/world aggregates are excluded from country
rows to prevent double counting.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
from zipfile import ZipFile

import httpx
import numpy as np
import pandas as pd
import pycountry
from sqlalchemy import delete, insert

from .db import SessionLocal, init_db
from .models import GlobalCropStatistic


URL = (
    "https://bulks-faostat.fao.org/production/"
    "Production_Crops_Livestock_E_All_Data_(Normalized).zip"
)
AREA_ELEMENTS = {"Area harvested", "Harvested area"}
ELEMENTS = {
    "Area harvested": "area",
    "Harvested area": "area",
    "Production": "production",
    "Yield": "yield",
}
USE_COLUMNS = {
    "Area Code (M49)", "Area", "Item Code", "Item",
    "Element", "Year", "Unit", "Value", "Flag",
}
CORE_FAOSTAT_ITEM_CODES = {
    "015": "WHEAT",
    "056": "MAIZE",
    "027": "RICE",
    "236": "SOYBEAN",
}
CHUNK_SIZE = 200_000


def clean_numeric_code(value) -> str | None:
    """Normalize FAOSTAT codes such as the literal string "'004"."""
    if value is None or pd.isna(value):
        return None
    raw = str(value).strip().lstrip("'").strip()
    if raw.endswith(".0"):
        raw = raw[:-2]
    if not raw or not raw.isdigit():
        return None
    return raw.zfill(3)


def country_iso3_from_m49(value) -> str | None:
    numeric = clean_numeric_code(value)
    if not numeric:
        return None
    try:
        country = pycountry.countries.get(numeric=numeric)
        return country.alpha_3 if country else None
    except (AttributeError, LookupError, ValueError):
        return None


def faostat_crop_code(item_code, item_name: str) -> str:
    """Use familiar aliases for core crops and stable FAO IDs for all others."""
    code = clean_numeric_code(item_code)
    if not code:
        raise ValueError(f"FAOSTAT Item Code yaroqsiz: {item_code!r}")
    # Only map item IDs with verified one-to-one identities. Do not merge
    # similarly named FAOSTAT products into one crop and double-count area.
    return CORE_FAOSTAT_ITEM_CODES.get(code, f"FAO_{int(code)}")


def convert_value(value, unit: str, kind: str) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number) or number < 0:
        return None

    normalized_unit = re.sub(r"\s+", " ", str(unit).lower()).strip()
    if kind == "area":
        if normalized_unit == "1000 ha":
            return number * 1000.0
        if normalized_unit == "ha":
            return number
    elif kind == "production":
        if normalized_unit in {"1000 t", "1000 tonnes", "1000 tonne"}:
            return number * 1000.0
        if normalized_unit in {"t", "tonnes", "tonne"}:
            return number
    elif kind == "yield":
        if normalized_unit == "hg/ha":
            return number / 10_000.0
        if normalized_unit == "kg/ha":
            return number / 1_000.0
        if normalized_unit in {"t/ha", "tonnes/ha"}:
            return number
    return None


def _choose_encoding(csv_path: Path, chunksize: int) -> str:
    """Validate the lightweight first pass before yielding any imported rows."""
    for encoding in ("utf-8-sig", "latin-1"):
        try:
            for _ in pd.read_csv(
                csv_path,
                usecols=["Item Code", "Element"],
                dtype={"Item Code": "string", "Element": "string"},
                chunksize=chunksize,
                encoding=encoding,
            ):
                pass
            return encoding
        except UnicodeDecodeError:
            continue
    raise RuntimeError("FAOSTAT CSV encodingini aniqlab bo‘lmadi.")


def _detect_crop_item_codes(csv_path: Path, encoding: str, chunksize: int) -> set[str]:
    item_codes: set[str] = set()
    for chunk in pd.read_csv(
        csv_path,
        usecols=["Item Code", "Element"],
        dtype={"Item Code": "string", "Element": "string"},
        chunksize=chunksize,
        encoding=encoding,
    ):
        crop_rows = chunk["Element"].isin(AREA_ELEMENTS)
        item_codes.update(
            str(value).strip().lstrip("'")
            for value in chunk.loc[crop_rows, "Item Code"].dropna().unique()
        )
    if not item_codes:
        raise RuntimeError(
            "FAOSTAT faylida Area harvested / Harvested area elementi bo‘lgan item topilmadi."
        )
    return item_codes


def iter_faostat_csv(
    csv_path: str | Path,
    source_release: str = "FAOSTAT_2024",
    chunksize: int = CHUNK_SIZE,
):
    """Yield one country/item/year row at a time using temporary SQLite staging.

    The staging table combines Area, Production and Yield even when the source
    CSV chunk boundary falls between those element blocks. This avoids silently
    losing partial records at chunk boundaries and keeps RAM usage bounded.
    """
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"FAOSTAT CSV topilmadi: {path}")
    if chunksize < 1:
        raise ValueError("chunksize kamida 1 bo‘lishi kerak.")

    encoding = _choose_encoding(path, chunksize)
    crop_item_codes = _detect_crop_item_codes(path, encoding, chunksize)

    with tempfile.TemporaryDirectory(prefix="osh-faostat-stage-", dir=path.parent) as temp_dir:
        stage_path = Path(temp_dir) / "faostat_stage.sqlite3"
        connection = sqlite3.connect(stage_path)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("""
                CREATE TABLE staged (
                    area_m49 TEXT NOT NULL,
                    area_name TEXT NOT NULL,
                    item_code TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    year INTEGER NOT NULL,
                    harvested_area_ha REAL,
                    production_t REAL,
                    yield_t_ha REAL,
                    area_flag TEXT,
                    production_flag TEXT,
                    yield_flag TEXT,
                    PRIMARY KEY (area_m49, item_code, year)
                )
            """)

            upsert_sql = """
                INSERT INTO staged (
                    area_m49, area_name, item_code, item_name, year,
                    harvested_area_ha, production_t, yield_t_ha,
                    area_flag, production_flag, yield_flag
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(area_m49, item_code, year) DO UPDATE SET
                    area_name=excluded.area_name,
                    item_name=excluded.item_name,
                    harvested_area_ha=COALESCE(excluded.harvested_area_ha, staged.harvested_area_ha),
                    production_t=COALESCE(excluded.production_t, staged.production_t),
                    yield_t_ha=COALESCE(excluded.yield_t_ha, staged.yield_t_ha),
                    area_flag=COALESCE(excluded.area_flag, staged.area_flag),
                    production_flag=COALESCE(excluded.production_flag, staged.production_flag),
                    yield_flag=COALESCE(excluded.yield_flag, staged.yield_flag)
            """

            for chunk in pd.read_csv(
                path,
                usecols=lambda column: column in USE_COLUMNS,
                dtype={"Area Code (M49)": "string", "Item Code": "string"},
                chunksize=chunksize,
                encoding=encoding,
            ):
                missing = USE_COLUMNS.difference(chunk.columns)
                missing.discard("Flag")
                if missing:
                    raise RuntimeError(
                        f"FAOSTAT ustunlari yetishmaydi: {sorted(missing)}"
                    )
                if "Flag" not in chunk.columns:
                    chunk["Flag"] = None

                chunk = chunk[
                    chunk["Item Code"].astype("string").str.strip().str.lstrip("'").isin(crop_item_codes)
                    & chunk["Element"].isin(ELEMENTS)
                ]
                if chunk.empty:
                    continue

                staged_rows = []
                for row in chunk.to_dict(orient="records"):
                    m49 = clean_numeric_code(row.get("Area Code (M49)"))
                    item_code = clean_numeric_code(row.get("Item Code"))
                    try:
                        year = int(row.get("Year"))
                    except (TypeError, ValueError):
                        continue
                    if not m49 or not item_code:
                        continue

                    kind = ELEMENTS[row["Element"]]
                    value = convert_value(row.get("Value"), row.get("Unit"), kind)
                    if value is None:
                        continue

                    flag_value = row.get("Flag")
                    flag = (
                        str(flag_value).strip()
                        if flag_value is not None and not pd.isna(flag_value)
                        and str(flag_value).strip()
                        else None
                    )
                    area_value = production_value = yield_value = None
                    area_flag = production_flag = yield_flag = None
                    if kind == "area":
                        area_value, area_flag = value, flag
                    elif kind == "production":
                        production_value, production_flag = value, flag
                    else:
                        yield_value, yield_flag = value, flag

                    staged_rows.append((
                        m49, str(row["Area"]), item_code, str(row["Item"]),
                        year, area_value, production_value, yield_value,
                        area_flag, production_flag, yield_flag,
                    ))

                if staged_rows:
                    connection.executemany(upsert_sql, staged_rows)
                    connection.commit()

            cursor = connection.execute("""
                SELECT area_m49, area_name, item_code, item_name, year,
                       harvested_area_ha, production_t, yield_t_ha,
                       area_flag, production_flag, yield_flag
                FROM staged
                ORDER BY area_m49, item_code, year
            """)
            for row in cursor:
                (
                    m49, area_name, item_code, item_name, year,
                    area, production, yield_value,
                    area_flag, production_flag, yield_flag,
                ) = row
                iso3 = country_iso3_from_m49(m49)
                if not iso3:
                    # Exclude World/region aggregates; country-level rows only.
                    continue

                if area is None and production is not None and yield_value is not None and yield_value > 0:
                    area = production / yield_value
                    area_flag = "DERIVED_FROM_PRODUCTION_AND_YIELD"
                if yield_value is None and area is not None and area > 0 and production is not None:
                    yield_value = production / area
                    yield_flag = "DERIVED_FROM_PRODUCTION_AND_AREA"

                if area is None and production is None and yield_value is None:
                    continue

                yield {
                    "source_code": "FAOSTAT_QCL",
                    "source_release": str(source_release)[:32],
                    "area_m49": m49,
                    "country_iso3": iso3,
                    "area_name": str(area_name),
                    "item_code": item_code,
                    "crop_code": faostat_crop_code(item_code, str(item_name)),
                    "crop_name": str(item_name),
                    "year": int(year),
                    "harvested_area_ha": float(area) if area is not None else None,
                    "production_t": float(production) if production is not None else None,
                    "yield_t_ha": float(yield_value) if yield_value is not None else None,
                    "area_flag": area_flag,
                    "production_flag": production_flag,
                    "yield_flag": yield_flag,
                    "imported_at": datetime.now(timezone.utc),
                }
        finally:
            connection.close()


def parse_faostat_csv(
    csv_path: str | Path,
    source_release: str = "FAOSTAT_2024",
    chunksize: int = CHUNK_SIZE,
) -> list[dict]:
    """Convenience parser for tests/small files. Production import is streamed."""
    return list(iter_faostat_csv(csv_path, source_release, chunksize))


def parse_faostat_zip(payload: bytes, source_release: str = "FAOSTAT_2024") -> list[dict]:
    """Backward-compatible ZIP parser used by tests and external scripts."""
    with tempfile.TemporaryDirectory(prefix="osh-faostat-zip-") as temp_dir:
        with ZipFile(BytesIO(payload)) as archive:
            csv_name = next(
                (
                    name for name in archive.namelist()
                    if name.lower().endswith("all_data_(normalized).csv")
                ),
                None,
            )
            if not csv_name:
                raise RuntimeError("FAOSTAT ZIP ichida normalized All_Data CSV topilmadi.")
            csv_path = Path(temp_dir) / Path(csv_name).name
            with archive.open(csv_name) as source, csv_path.open("wb") as target:
                shutil.copyfileobj(source, target)
        return parse_faostat_csv(csv_path, source_release=source_release)


def _resolve_source_csv(args) -> tuple[Path, tempfile.TemporaryDirectory | None]:
    if args.csv:
        path = Path(args.csv).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"--csv fayli topilmadi: {path}")
        return path, None

    temp_dir = tempfile.TemporaryDirectory(prefix="osh-faostat-download-")
    try:
        print("Downloading official FAOSTAT QCL bulk dataset...", flush=True)
        with httpx.Client(timeout=300, follow_redirects=True) as client:
            response = client.get(URL)
            response.raise_for_status()
        archive_path = Path(temp_dir.name) / "faostat.zip"
        archive_path.write_bytes(response.content)
        with ZipFile(archive_path) as archive:
            csv_name = next(
                (
                    name for name in archive.namelist()
                    if name.lower().endswith("all_data_(normalized).csv")
                ),
                None,
            )
            if not csv_name:
                raise RuntimeError("FAOSTAT ZIP ichida normalized All_Data CSV topilmadi.")
            csv_path = Path(temp_dir.name) / Path(csv_name).name
            with archive.open(csv_name) as source, csv_path.open("wb") as target:
                shutil.copyfileobj(source, target)
        return csv_path, temp_dir
    except Exception:
        temp_dir.cleanup()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description="Import all FAOSTAT crop-history rows into PostgreSQL.")
    parser.add_argument("--csv", help="Already downloaded normalized FAOSTAT CSV path.")
    parser.add_argument("--source-release", default="FAOSTAT_2024")
    parser.add_argument("--chunksize", type=int, default=CHUNK_SIZE)
    args = parser.parse_args(argv)

    init_db()
    csv_path, cleanup = _resolve_source_csv(args)
    try:
        print(f"Reading FAOSTAT CSV: {csv_path}", flush=True)
        records = iter_faostat_csv(
            csv_path,
            source_release=args.source_release,
            chunksize=args.chunksize,
        )

        counts = Counter()
        total = 0
        with SessionLocal() as db:
            with db.begin():
                first = next(records, None)
                if first is None:
                    raise RuntimeError(
                        "Mos FAOSTAT crop qatorlari topilmadi. Eski global jadval o‘zgartirilmadi."
                    )

                # Replace the old FAOSTAT snapshot only after at least one valid row exists.
                db.execute(
                    delete(GlobalCropStatistic).where(
                        GlobalCropStatistic.source_code == "FAOSTAT_QCL"
                    )
                )
                batch = [first]
                for record in records:
                    batch.append(record)
                    if len(batch) >= 2_000:
                        db.execute(insert(GlobalCropStatistic), batch)
                        for item in batch:
                            counts[item["crop_code"]] += 1
                        total += len(batch)
                        batch.clear()

                if batch:
                    db.execute(insert(GlobalCropStatistic), batch)
                    for item in batch:
                        counts[item["crop_code"]] += 1
                    total += len(batch)

        print("FAOSTAT crop history import completed:", flush=True)
        print(f"Rows imported: {total:,}", flush=True)
        print(f"Distinct crop items: {len(counts):,}", flush=True)
        print(f"First/last year in source: 1961–2024 (verify from API after import)", flush=True)
        for crop, count in sorted(counts.items()):
            print(f"  {crop}: {count:,} rows", flush=True)
        print(
            "Source: FAOSTAT QCL · CC BY 4.0 · https://www.fao.org/faostat/en/#data/QCL",
            flush=True,
        )
    finally:
        if cleanup is not None:
            cleanup.cleanup()


if __name__ == "__main__":
    main()
