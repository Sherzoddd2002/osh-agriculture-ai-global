"""Build the public, static UZB ADM1/ADM2 bundle for GitHub Pages.

The public browser never calls the Fly/FastAPI boundary endpoint. GitHub Actions
fetches geoBoundaries, validates every polygon, and places the files in docs/.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shapely.geometry import shape
from backend.app.services.boundaries import get_boundary_geojson

OUTPUT = ROOT / "docs" / "data" / "boundaries"
EXPECTED_FEATURES = {"ADM1": 14, "ADM2": 199}


async def fetch_level(level: str) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            result = await get_boundary_geojson("UZB", level)
            if result.get("type") != "FeatureCollection":
                raise ValueError(f"UZB {level}: response is not FeatureCollection")
            features = result.get("features")
            if not isinstance(features, list) or len(features) != EXPECTED_FEATURES[level]:
                raise ValueError(
                    f"UZB {level}: expected exactly {EXPECTED_FEATURES[level]} polygons, "
                    f"received {len(features) if isinstance(features, list) else 'not a list'}"
                )

            valid = []
            for index, feature in enumerate(features):
                if not isinstance(feature, dict) or not isinstance(feature.get("geometry"), dict):
                    raise ValueError(f"UZB {level}: feature {index} has no geometry")
                geometry = shape(feature["geometry"])
                if geometry.is_empty or not geometry.is_valid or geometry.geom_type not in {
                    "Polygon", "MultiPolygon"
                }:
                    raise ValueError(f"UZB {level}: invalid polygon at feature {index}")
                valid.append(feature)

            if len(valid) != len(features):
                raise ValueError(f"UZB {level}: polygon validation count mismatch")

            metadata = result.get("metadata") or {}
            if metadata.get("country_iso3") != "UZB" or metadata.get("admin_level") != level:
                raise ValueError(f"UZB {level}: metadata identity mismatch: {metadata!r}")
            return result
        except Exception as exc:
            last_error = exc
            if attempt < 3:
                await asyncio.sleep(attempt * 3)
    raise RuntimeError(f"Could not build UZB {level} after 3 attempts: {last_error}")



SIAT_WHEAT_PRODUCTION_URL = (
    "https://api.siat.stat.uz/media/uploads/sdmx/sdmx_data_1458.json"
)
SIAT_WHEAT_AREA_URL = (
    "https://api.siat.stat.uz/media/uploads/sdmx/sdmx_data_2761.json"
)
OFFICIAL_YIELD_OUTPUT = ROOT / "docs" / "data" / "official-yield"
YEARS = tuple(range(2010, 2025))


def _siat_document(payload: object, expected_code: str, expected_unit: str) -> dict:
    if isinstance(payload, list) and len(payload) == 1:
        payload = payload[0]
    if not isinstance(payload, dict):
        raise ValueError(f"SIAT {expected_code}: response must be a one-item data object")
    metadata = payload.get("metadata") or []
    values = {
        row.get("name_en"): row.get("value_en")
        for row in metadata
        if isinstance(row, dict)
    }
    if values.get("Indicator identification number (code)") != expected_code:
        raise ValueError(
            f"SIAT indicator code mismatch: expected {expected_code}, "
            f"received {values.get('Indicator identification number (code)')!r}"
        )
    if values.get("Unit of measurement") != expected_unit:
        raise ValueError(
            f"SIAT {expected_code} unit mismatch: "
            f"expected {expected_unit!r}, received {values.get('Unit of measurement')!r}"
        )
    records = payload.get("data")
    if not isinstance(records, list) or not records:
        raise ValueError(f"SIAT {expected_code}: data array is missing")
    return {"metadata": values, "records": records}


async def build_official_wheat_yield(client: httpx.AsyncClient) -> dict:
    """Build official ADM1 wheat yield (t/ha) from SIAT production and sown area.

    SIAT wheat production is reported in thousand tonnes; wheat sown area is
    reported in hectares. District-level wheat production is not supplied by
    these two tables, so this bundle intentionally contains ADM1 provinces only.
    """
    production_response, area_response = await asyncio.gather(
        client.get(SIAT_WHEAT_PRODUCTION_URL),
        client.get(SIAT_WHEAT_AREA_URL),
    )
    production_response.raise_for_status()
    area_response.raise_for_status()
    production_doc = _siat_document(
        production_response.json(), "1.03.03.0010", "thousand tons"
    )
    area_doc = _siat_document(
        area_response.json(), "1.03.03.0084", "hectare"
    )

    production = {
        str(row.get("Code")): row
        for row in production_doc["records"]
        if isinstance(row, dict) and row.get("Code") is not None
    }
    areas = {
        str(row.get("Code")): row
        for row in area_doc["records"]
        if isinstance(row, dict) and row.get("Code") is not None
    }
    if not production or not areas:
        raise ValueError("SIAT wheat records could not be keyed by administrative code")

    regions = []
    for code in sorted(set(production) & set(areas)):
        p_row, a_row = production[code], areas[code]
        if code == "1700":
            continue
        name = " ".join(str(p_row.get("Klassifikator") or "").split())
        area_name = " ".join(str(a_row.get("Klassifikator") or "").split())
        if not name or name != area_name:
            raise ValueError(
                f"SIAT administrative labels differ for code {code}: "
                f"{name!r} vs {area_name!r}"
            )

        rows = []
        for year in YEARS:
            production_thousand_t = p_row.get(str(year))
            area_ha = a_row.get(str(year))
            if production_thousand_t is None or area_ha is None:
                continue
            production_thousand_t = float(production_thousand_t)
            area_ha = float(area_ha)
            if production_thousand_t <= 0 or area_ha <= 0:
                continue
            production_t = production_thousand_t * 1000.0
            yield_t_ha = production_t / area_ha
            if not (0 < yield_t_ha < 30):
                raise ValueError(
                    f"Implausible official wheat yield for {name}, {year}: {yield_t_ha}"
                )
            rows.append(
                {
                    "year": year,
                    "yield": round(yield_t_ha, 6),
                    "production_t": round(production_t, 3),
                    "sown_area_ha": round(area_ha, 3),
                }
            )

        if len(rows) >= 12:
            regions.append(
                {
                    "admin_code": code,
                    "name_uz": name,
                    "records": rows,
                }
            )

    if len(regions) != 13:
        raise ValueError(
            f"SIAT ADM1 wheat dataset should contain 13 agricultural regions, "
            f"received {len(regions)}"
        )
    for region in regions:
        years = [row["year"] for row in region["records"]]
        if len(years) != len(set(years)) or len(years) < 12:
            raise ValueError(
                f"SIAT wheat series is incomplete or duplicated for {region['name_uz']}"
            )

    return {
        "country_iso3": "UZB",
        "admin_level": "ADM1",
        "crop_code": "whea",
        "crop_name_uz": "Bug‘doy",
        "unit": "tonnes per hectare",
        "years": [YEARS[0], YEARS[-1]],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": (
            "official wheat production (thousand tonnes) * 1000 / "
            "official wheat sown area (hectares)"
        ),
        "sources": [
            {
                "indicator_code": "1.03.03.0010",
                "name": "Wheat production in all categories of farms",
                "unit": "thousand tons",
                "url": "https://siat.stat.uz/data/1458/?lang=en",
                "raw_url": SIAT_WHEAT_PRODUCTION_URL,
                "updated": production_doc["metadata"].get("Last modified date"),
            },
            {
                "indicator_code": "1.03.03.0084",
                "name": "Sown area of wheat in all categories of farms",
                "unit": "hectare",
                "url": "https://siat.stat.uz/data/2761/?lang=en",
                "raw_url": SIAT_WHEAT_AREA_URL,
                "updated": area_doc["metadata"].get("Last modified date"),
            },
        ],
        "license": "CC BY 4.0",
        "geographic_coverage": "13 agricultural ADM1 regions; Tashkent city excluded",
        "district_yield_available": False,
        "regions": sorted(regions, key=lambda region: region["name_uz"]),
    }


async def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
        official_wheat = await build_official_wheat_yield(client)
    OFFICIAL_YIELD_OUTPUT.mkdir(parents=True, exist_ok=True)
    official_target = OFFICIAL_YIELD_OUTPUT / "UZB_ADM1_WHEA_2010_2024.json"
    official_target.write_text(
        json.dumps(official_wheat, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(
        "PASS SIAT ADM1 wheat yield: "
        f"{len(official_wheat['regions'])} regions, "
        f"{sum(len(region['records']) for region in official_wheat['regions'])} yearly records"
    )
    manifest = {
        "country_iso3": "UZB",
        "country_name": "Uzbekistan",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "delivery": "GitHub Pages static GeoJSON; no runtime API required",
        "levels": {},
        "official_yield": {
            "file": "official-yield/UZB_ADM1_WHEA_2010_2024.json",
            "crop": "whea",
            "admin_level": "ADM1",
            "region_count": len(official_wheat["regions"]),
            "record_count": sum(len(region["records"]) for region in official_wheat["regions"]),
            "license": official_wheat["license"],
        },
    }

    for level in ("ADM1", "ADM2"):
        payload = await fetch_level(level)
        metadata = payload.get("metadata") or {}
        target = OUTPUT / f"UZB_{level}.geojson"
        public_payload = {
            "type": "FeatureCollection",
            "features": payload["features"],
            "metadata": metadata,
        }
        target.write_text(
            json.dumps(public_payload, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        manifest["levels"][level] = {
            "file": f"boundaries/UZB_{level}.geojson",
            "feature_count": len(payload["features"]),
            "valid_polygon_count": len(payload["features"]),
            "source": metadata.get("source"),
            "source_url": metadata.get("source_url"),
            "boundary_year": metadata.get("boundary_year"),
            "license": metadata.get("license"),
            "boundary_name": metadata.get("boundary_name"),
            "boundary_id": metadata.get("boundary_id"),
        }
        print(
            f"PASS UZB {level}: {len(payload['features'])} valid polygons | "
            f"{metadata.get('source')} | {metadata.get('license')}"
        )

    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
