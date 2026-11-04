"""Chunked FAOSTAT QCL bulk importer for the central PostgreSQL database.

Run from E:\\OSH\\AgricultureAI\\source\\backend:
    python -m app.sync_global_data
"""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from zipfile import ZipFile
import re

import httpx
import numpy as np
import pandas as pd
import pycountry
from sqlalchemy import delete, insert

from .db import SessionLocal, init_db
from .models import GlobalCropStatistic
from .services.global_crops import normalize_crop_code


URL = (
    "https://bulks-faostat.fao.org/production/"
    "Production_Crops_Livestock_E_All_Data_(Normalized).zip"
)
CROP_CODES = {
    "WHEAT", "MAIZE", "RICE", "BARLEY",
    "SOYBEAN", "COTTON", "POTATO", "SORGHUM",
}
ELEMENTS = {
    "Area harvested": "area",
    "Harvested area": "area",
    "Production": "production",
    "Yield": "yield",
}
KEY_COLUMNS = [
    "Area Code (M49)", "Area", "Item Code", "Item", "crop_code", "Year"
]
USE_COLUMNS = set(KEY_COLUMNS + ["Element", "Unit", "Value", "Flag"])


def country_iso3_from_m49(value) -> str | None:
    raw = str(value).strip()
    if raw.endswith(".0"):
        raw = raw[:-2]
    numeric = raw.zfill(3)
    try:
        country = pycountry.countries.get(numeric=numeric)
        return country.alpha_3 if country else None
    except (AttributeError, LookupError, ValueError):
        return None


def convert_value(value, unit: str, kind: str) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    normalized_unit = re.sub(r"\\s+", " ", str(unit).lower()).strip()

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
            return number / 10000.0
        if normalized_unit == "kg/ha":
            return number / 1000.0
        if normalized_unit in {"t/ha", "tonnes/ha"}:
            return number
    return None


def _iter_csv_chunks(archive: ZipFile, csv_name: str, encoding: str):
    with archive.open(csv_name) as source:
        yield from pd.read_csv(
            source,
            encoding=encoding,
            low_memory=False,
            chunksize=200_000,
            usecols=lambda column: column in USE_COLUMNS,
            dtype={"Area Code (M49)": "string", "Item Code": "string"},
        )


def parse_faostat_zip(payload: bytes, source_release: str = "bulk-latest") -> list[dict]:
    """Parse a FAOSTAT normalized ZIP without loading the full 4M+ row CSV."""
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

        def parse_with_encoding(encoding: str) -> list[dict]:
            output = []
            for chunk in _iter_csv_chunks(archive, csv_name, encoding):
                missing = USE_COLUMNS.difference(chunk.columns)
                if missing:
                    # Flag is optional in some historical extracts.
                    missing.discard("Flag")
                    if missing:
                        raise RuntimeError(
                            f"FAOSTAT ustunlari yetishmaydi: {sorted(missing)}"
                        )
                    if "Flag" not in chunk:
                        chunk["Flag"] = None

                chunk = chunk[chunk["Element"].isin(ELEMENTS)].copy()
                if chunk.empty:
                    continue
                chunk["kind"] = chunk["Element"].map(ELEMENTS)
                chunk["crop_code"] = chunk["Item"].map(normalize_crop_code)
                chunk = chunk[chunk["crop_code"].isin(CROP_CODES)].copy()
                if chunk.empty:
                    continue

                chunk["value_norm"] = [
                    convert_value(value, unit, kind)
                    for value, unit, kind in zip(
                        chunk["Value"], chunk["Unit"], chunk["kind"]
                    )
                ]
                chunk = chunk[chunk["value_norm"].notna()].copy()
                if chunk.empty:
                    continue

                for key, group in chunk.groupby(KEY_COLUMNS, dropna=False, sort=False):
                    values = {}
                    flags = {}
                    for row in group.itertuples(index=False):
                        kind = row.kind
                        values[kind] = float(row.value_norm)
                        flag = getattr(row, "Flag", None)
                        if flag is not None and not pd.isna(flag):
                            flags[kind] = str(flag)

                    area = values.get("area")
                    production = values.get("production")
                    yield_value = values.get("yield")
                    area_flag = flags.get("area")
                    yield_flag = flags.get("yield")

                    if area is None and production is not None and yield_value and yield_value > 0:
                        area = production / yield_value
                        area_flag = "DERIVED_FROM_PRODUCTION_AND_YIELD"
                    if yield_value is None and area and area > 0 and production is not None:
                        yield_value = production / area
                        yield_flag = "DERIVED_FROM_PRODUCTION_AND_AREA"
                    if area is None or area <= 0 or yield_value is None:
                        continue
                    if not 0 <= yield_value <= 30:
                        continue

                    m49, area_name, item_code, crop_name, crop_code, year = key
                    iso3 = country_iso3_from_m49(m49)
                    if not iso3:
                        # Skip world/region aggregates here; global totals are
                        # recomputed from country rows to avoid double counting.
                        continue

                    output.append({
                        "source_code": "FAOSTAT_QCL",
                        "source_release": source_release[:32],
                        "area_m49": str(m49).strip().zfill(3),
                        "country_iso3": iso3,
                        "area_name": str(area_name),
                        "item_code": str(item_code),
                        "crop_code": str(crop_code),
                        "crop_name": str(crop_name),
                        "year": int(year),
                        "harvested_area_ha": float(area),
                        "production_t": (
                            float(production) if production is not None else None
                        ),
                        "yield_t_ha": float(yield_value),
                        "area_flag": area_flag,
                        "production_flag": flags.get("production"),
                        "yield_flag": yield_flag,
                        "imported_at": datetime.now(timezone.utc),
                    })
            return output

        try:
            records = parse_with_encoding("utf-8-sig")
        except UnicodeDecodeError:
            # FAOSTAT bulk domains are not uniformly encoded; retry from the
            # start with latin-1 so a partial UTF-8 pass cannot leak records.
            records = parse_with_encoding("latin-1")
        return records


def main():
    init_db()
    print("Downloading official FAOSTAT QCL bulk dataset...", flush=True)
    with httpx.Client(timeout=300, follow_redirects=True) as client:
        response = client.get(URL)
        response.raise_for_status()

    release = response.headers.get("Last-Modified") or datetime.now(
        timezone.utc
    ).date().isoformat()
    records = parse_faostat_zip(response.content, source_release=release)
    if not records:
        raise RuntimeError(
            "Mos FAOSTAT qatorlari topilmadi. Import bekor qilindi; oldingi global jadval saqlanadi."
        )

    print(f"Prepared {len(records):,} country-crop-year records.", flush=True)
    with SessionLocal() as db:
        # Delete + batched insert is one transaction: failures roll back and
        # preserve the previous completed snapshot.
        db.execute(
            delete(GlobalCropStatistic).where(
                GlobalCropStatistic.source_code == "FAOSTAT_QCL"
            )
        )
        for start in range(0, len(records), 2_000):
            db.execute(
                insert(GlobalCropStatistic),
                records[start:start + 2_000],
            )
        db.commit()

    counts = pd.Series([row["crop_code"] for row in records]).value_counts()
    print("FAOSTAT global crop import completed:", flush=True)
    for crop, count in counts.sort_index().items():
        print(f"  {crop}: {int(count):,} rows", flush=True)
    print("Source: FAOSTAT QCL · CC BY 4.0 · https://www.fao.org/faostat/en/#data/QCL", flush=True)


if __name__ == "__main__":
    main()
