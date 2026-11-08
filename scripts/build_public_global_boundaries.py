"""Build per-country global ADM1/ADM2 GeoJSON packages for GitHub Pages.

Uses geoBoundaries' gbOpen API and simplified GeoJSON downloads. Each country
is stored separately so the browser downloads only the selected country/level.
The existing UZB files are preserved because MAPSPAM joins them by shapeID.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from shapely import make_valid
from shapely.geometry import mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "data" / "boundaries" / "global"
WB_ARCGIS_BASE = "https://services.arcgis.com/iQ1dY19aHwbSDYIF/arcgis/rest/services/World_Bank_Global_Administrative_Divisions/FeatureServer"
WB_LAYER_IDS = {"ADM1": 2, "ADM2": 3}
WB_CATALOG_URL = "https://datacatalog.worldbank.org/search/dataset/0038272/world-bank-official-boundaries"
WB_UPDATED = "2026-10-21"
API_BASE = "https://geoboundaries-dev.org/api/current/gbOpen/ALL"
LEVELS = ("ADM1", "ADM2")
MIN_COUNTRIES_PER_LEVEL = 100
MAX_TOTAL_BYTES = 850 * 1024 * 1024
MAX_CONCURRENCY = 12


def read_json(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def valid_cached_package(path: Path, iso: str, level: str) -> dict | None:
    payload = read_json(path)
    if not payload or payload.get("type") != "FeatureCollection":
        return None
    metadata = payload.get("metadata") or {}
    features = payload.get("features")
    if (
        metadata.get("country_iso3") != iso
        or metadata.get("admin_level") != level
        or not isinstance(features, list)
        or not features
    ):
        return None
    return payload


def feature_name(properties: dict[str, Any]) -> str:
    for key in ("shapeName", "shape_name", "shapeNameEn", "NAME_1", "NAME_2", "name", "NAME", "admin"):
        value = properties.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def polygon_parts(geometry):
    """Return polygon components from Polygon/MultiPolygon/GeometryCollection."""
    if geometry is None or geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry] if geometry.area > 0 else []
    parts = []
    for child in getattr(geometry, "geoms", []):
        parts.extend(polygon_parts(child))
    return parts


def repair_polygon_geometry(geometry):
    """Repair common invalid source polygons without losing polygonal components."""
    candidate = geometry if geometry.is_valid else make_valid(geometry)
    parts = polygon_parts(candidate)
    if not parts:
        raise ValueError("geometry repair produced no polygonal area")
    repaired = unary_union(parts)
    if not repaired.is_valid:
        repaired = make_valid(repaired)
        parts = polygon_parts(repaired)
        if not parts:
            raise ValueError("geometry remains invalid after make_valid")
        repaired = unary_union(parts)
    if repaired.is_empty or not repaired.is_valid or repaired.geom_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError("geometry is not a valid Polygon/MultiPolygon after repair")
    return repaired


def validate_and_prepare(record: dict, level: str, source: dict) -> dict:
    iso = str(record.get("boundaryISO") or "").upper()
    if not re.fullmatch(r"[A-Z]{3}", iso):
        raise ValueError(f"Invalid ISO-3 code: {iso!r}")
    payload = source
    if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise ValueError(f"{iso} {level}: GeoJSON is not a FeatureCollection")

    prepared = []
    identifiers: set[str] = set()
    repaired_count = 0
    generated_name_count = 0
    for index, original in enumerate(payload["features"]):
        if not isinstance(original, dict) or not isinstance(original.get("geometry"), dict):
            raise ValueError(f"{iso} {level}: feature {index} has no geometry")
        geometry = shape(original["geometry"])
        if geometry.is_empty or geometry.geom_type not in {"Polygon", "MultiPolygon"}:
            raise ValueError(f"{iso} {level}: feature {index} is not a non-empty polygon")
        if not geometry.is_valid:
            geometry = repair_polygon_geometry(geometry)
            repaired_count += 1
        elif geometry.geom_type not in {"Polygon", "MultiPolygon"}:
            geometry = repair_polygon_geometry(geometry)
            repaired_count += 1

        feature = dict(original)
        feature["geometry"] = mapping(geometry)
        properties = dict(feature.get("properties") or {})
        shape_id = str(properties.get("shapeID") or properties.get("shape_id") or "").strip()
        name = feature_name(properties)
        if not name:
            stable_id = shape_id or str(feature.get("id") or "")
            name = f"Unnamed administrative area {stable_id or index + 1}"
            properties["name_quality"] = "generated_from_boundary_id"
            generated_name_count += 1
        if shape_id and shape_id in identifiers:
            raise ValueError(f"{iso} {level}: duplicate shape ID {shape_id}")
        if shape_id:
            identifiers.add(shape_id)
        if not feature_name(properties):
            properties["shapeName"] = name
        else:
            properties.setdefault("shapeName", name)
        properties["shapeType"] = level
        properties["countryISO3"] = iso
        feature["properties"] = properties
        prepared.append(feature)

    if not prepared:
        raise ValueError(f"{iso} {level}: no valid polygon features")

    metadata = {
        "country_iso3": iso,
        "country_name": str(record.get("boundaryName") or iso),
        "admin_level": level,
        "boundary_year": str(record.get("boundaryYearRepresented") or ""),
        "boundary_id": str(record.get("boundaryID") or ""),
        "source": str(record.get("boundarySource") or "geoBoundaries"),
        "source_url": str(record.get("boundarySourceURL") or ""),
        "license": str(record.get("boundaryLicense") or "See source metadata"),
        "license_detail": str(record.get("licenseDetail") or ""),
        "license_source": str(record.get("licenseSource") or ""),
        "continent": str(record.get("Continent") or "Unknown"),
        "source_version": "geoBoundaries current / gbOpen",
        "geometry_detail": "simplifiedGeometryGeoJSON" if record.get("simplifiedGeometryGeoJSON") else "gjDownloadURL",
        "feature_count": len(prepared),
        "geometry_repaired_count": repaired_count,
        "generated_name_count": generated_name_count,
        "attribution": "geoBoundaries; retain the source/license fields for each boundary",
    }
    return {"type": "FeatureCollection", "features": prepared, "metadata": metadata}


async def get_json(client: httpx.AsyncClient, url: str, semaphore: asyncio.Semaphore, params: dict | None = None) -> Any:
    last_error: Exception | None = None
    async with semaphore:
        for attempt in range(1, 4):
            try:
                response = await client.get(url, params=params, headers={"Accept": "application/json, application/geo+json"})
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                last_error = exc
                if attempt < 3:
                    await asyncio.sleep(attempt * 2)
    raise RuntimeError(f"GET failed: {url}: {last_error}")


def old_level_records(old_manifest: dict | None, level: str) -> dict[str, dict]:
    if not old_manifest:
        return {}
    result = {}
    for iso, country in (old_manifest.get("countries") or {}).items():
        record = ((country.get("levels") or {}).get(level))
        if record:
            result[iso] = record
    return result


async def build_level(
    client: httpx.AsyncClient,
    level: str,
    semaphore: asyncio.Semaphore,
    old_manifest: dict | None,
) -> tuple[dict[str, dict], list[str]]:
    api_url = f"{API_BASE}/{level}/"
    try:
        records = await get_json(client, api_url, semaphore)
        if isinstance(records, dict):
            records = [records]
        if not isinstance(records, list):
            raise ValueError(f"{level}: global API response is not a list")
    except Exception as exc:
        cached = old_level_records(old_manifest, level)
        if len(cached) < MIN_COUNTRIES_PER_LEVEL:
            raise RuntimeError(f"{level}: API failed and global cache is incomplete: {exc}") from exc
        print(f"WARN {level}: API unavailable; reusing {len(cached)} validated cached country packages")
        return cached, []

    by_iso: dict[str, dict] = {}
    for record in records:
        if not isinstance(record, dict):
            continue
        iso = str(record.get("boundaryISO") or "").upper()
        if not re.fullmatch(r"[A-Z]{3}", iso) or iso == "UZB":
            continue
        if iso in by_iso:
            raise ValueError(f"{level}: duplicate geoBoundaries metadata row for {iso}")
        by_iso[iso] = record
    if len(by_iso) < MIN_COUNTRIES_PER_LEVEL:
        cached = old_level_records(old_manifest, level)
        if len(cached) >= MIN_COUNTRIES_PER_LEVEL:
            print(f"WARN {level}: only {len(by_iso)} API countries; retaining {len(cached)} cached packages")
            return cached, []
        raise ValueError(f"{level}: unexpectedly low global coverage: {len(by_iso)} countries")

    old_records = old_level_records(old_manifest, level)
    results: dict[str, dict] = {}
    failures: list[str] = []

    async def build_one(iso: str, record: dict) -> None:
        path = OUTPUT / f"{iso}_{level}.geojson"
        cached = valid_cached_package(path, iso, level)
        boundary_id = str(record.get("boundaryID") or "")
        old_meta = old_records.get(iso) or {}
        if cached and boundary_id and old_meta.get("boundary_id") == boundary_id:
            results[iso] = old_meta
            return

        try:
            # The ALL listing may omit single-boundary download links. Resolve
            # that country's own metadata row before giving up on the package.
            boundary_record = dict(record)
            download_url = str(
                boundary_record.get("simplifiedGeometryGeoJSON")
                or boundary_record.get("gjDownloadURL")
                or ""
            )
            if not download_url.startswith("https://"):
                country_api = f"https://geoboundaries-dev.org/api/current/gbOpen/{iso}/{level}/"
                detail = await get_json(client, country_api, semaphore)
                if isinstance(detail, list):
                    if not detail:
                        raise ValueError("single-country metadata endpoint returned an empty list")
                    detail = detail[0]
                if not isinstance(detail, dict):
                    raise ValueError("single-country metadata endpoint returned an invalid response")
                boundary_record.update(detail)
                download_url = str(
                    boundary_record.get("simplifiedGeometryGeoJSON")
                    or boundary_record.get("gjDownloadURL")
                    or ""
                )
            if not download_url.startswith("https://"):
                raise ValueError("no HTTPS GeoJSON download URL in boundary metadata")
            source = await get_json(client, download_url, semaphore)
            prepared = validate_and_prepare(boundary_record, level, source)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(prepared, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            meta = prepared["metadata"]
            results[iso] = {
                "file": f"boundaries/global/{iso}_{level}.geojson",
                "feature_count": meta["feature_count"],
                "boundary_id": meta["boundary_id"],
                "boundary_year": meta["boundary_year"],
                "country_name": meta["country_name"],
                "source": meta["source"],
                "source_url": meta["source_url"],
                "license": meta["license"],
                "license_detail": meta["license_detail"],
                "license_source": meta["license_source"],
                "continent": meta["continent"],
                "geometry_detail": meta["geometry_detail"],
            }
        except Exception as exc:
            if cached:
                results[iso] = old_meta or {
                    "file": f"boundaries/global/{iso}_{level}.geojson",
                    "feature_count": len(cached["features"]),
                    "boundary_id": cached["metadata"].get("boundary_id", ""),
                    "boundary_year": cached["metadata"].get("boundary_year", ""),
                    "country_name": cached["metadata"].get("country_name", iso),
                    "source": cached["metadata"].get("source", "geoBoundaries"),
                    "source_url": cached["metadata"].get("source_url", ""),
                    "license": cached["metadata"].get("license", ""),
                    "license_detail": cached["metadata"].get("license_detail", ""),
                    "license_source": cached["metadata"].get("license_source", ""),
                    "continent": cached["metadata"].get("continent", "Unknown"),
                    "geometry_detail": cached["metadata"].get("geometry_detail", "cached"),
                }
                print(f"WARN {iso}/{level}: source refresh failed; retained validated cache: {exc}")
            else:
                failures.append(f"{iso}/{level}: {exc}")

    await asyncio.gather(*(build_one(iso, record) for iso, record in by_iso.items()))
    if len(results) < MIN_COUNTRIES_PER_LEVEL:
        raise RuntimeError(f"{level}: only {len(results)} country packages survived validation")
    print(
        f"PASS GLOBAL {level}: {len(results)} country packages / "
        f"{sum(int(row.get('feature_count', 0)) for row in results.values()):,} admin polygons"
    )
    return results, failures


async def add_world_bank_fallback(
    client: httpx.AsyncClient,
    level: str,
    packages: dict[str, dict],
    semaphore: asyncio.Semaphore,
) -> dict[str, int]:
    """Fill missing country/level packages from the World Bank global boundary service."""
    layer_id = WB_LAYER_IDS[level]
    query_url = f"{WB_ARCGIS_BASE}/{layer_id}/query"

    # Ask for the list of ISO3 country codes that actually exist at this level.
    distinct = await get_json(
        client,
        query_url,
        semaphore,
        params={
            "where": "1=1",
            "outFields": "ISO_A3",
            "returnGeometry": "false",
            "returnDistinctValues": "true",
            "orderByFields": "ISO_A3",
            "f": "json",
        },
    )
    if not isinstance(distinct, dict) or distinct.get("error") or not isinstance(distinct.get("features"), list):
        raise RuntimeError(f"World Bank {level}: distinct-country query returned an invalid response: {distinct}")
    wb_codes = sorted({
        str((feature.get("attributes") or {}).get("ISO_A3") or "").strip().upper()
        for feature in distinct["features"]
        if re.fullmatch(r"[A-Z]{3}", str((feature.get("attributes") or {}).get("ISO_A3") or "").strip().upper())
    })
    missing_codes = [iso for iso in wb_codes if iso != "UZB" and iso not in packages]
    if not missing_codes:
        print(f"PASS WORLD BANK FALLBACK {level}: no missing gbOpen country packages found in WB-GAD")
        return {"country_count": 0, "feature_count": 0}

    print(
        f"INFO WORLD BANK {level}: {len(wb_codes)} ISO3 groups in WB-GAD; "
        f"{len(missing_codes)} missing from gbOpen: {missing_codes}"
    )

    # Only request missing countries. This avoids downloading the full 40k+ polygon layer.
    fields = (
        "FID,ISO_A3,ISO_A2,WB_A3,WB_STATUS,NAM_0,NAM_1,ADM1CD_c,ADM1CD,ADM1CD_t"
        if level == "ADM1"
        else "FID,ISO_A3,ISO_A2,WB_A3,WB_STATUS,NAM_0,NAM_1,NAM_2,ADM1CD_c,ADM2CD_c,ADM1CD,ADM2CD"
    )
    raw_features: list[dict] = []
    for start in range(0, len(missing_codes), 35):
        batch = missing_codes[start:start + 35]
        where = "ISO_A3 IN (" + ",".join("'" + iso + "'" for iso in batch) + ")"
        offset = 0
        while True:
            payload = await get_json(
                client,
                query_url,
                semaphore,
                params={
                    "where": where,
                    "outFields": fields,
                    "returnGeometry": "true",
                    "outSR": "4326",
                    "f": "geojson",
                    "orderByFields": "ISO_A3",
                    "resultOffset": offset,
                    "resultRecordCount": 1800,
                },
            )
            if (
                not isinstance(payload, dict)
                or payload.get("error")
                or payload.get("type") != "FeatureCollection"
                or not isinstance(payload.get("features"), list)
            ):
                raise RuntimeError(f"World Bank {level}: feature query failed: {payload}")
            page = payload["features"]
            raw_features.extend(page)
            exceeded = bool(payload.get("exceededTransferLimit"))
            del payload
            if not exceeded or not page:
                break
            offset += len(page)

    grouped: dict[str, list[dict]] = {}
    for feature in raw_features:
        properties = dict(feature.get("properties") or {})
        iso = str(properties.get("ISO_A3") or "").strip().upper()
        if iso not in missing_codes:
            continue
        source_name = (
            properties.get("NAM_1") if level == "ADM1" else properties.get("NAM_2")
        )
        source_name = str(source_name or "").strip()
        if not source_name:
            source_name = f"Unnamed {level} area {properties.get('FID') or len(grouped.get(iso, [])) + 1}"
        source_id = (
            properties.get("ADM1CD_c") or properties.get("ADM1CD") or properties.get("FID")
            if level == "ADM1"
            else properties.get("ADM2CD_c") or properties.get("ADM2CD") or properties.get("FID")
        )
        properties["shapeName"] = source_name
        properties["shapeID"] = f"{iso}-{level}-{source_id or len(grouped.get(iso, [])) + 1}"
        properties["countryISO3"] = iso
        properties["shapeType"] = level
        feature["properties"] = properties
        if feature.get("geometry"):
            grouped.setdefault(iso, []).append(feature)

    del raw_features
    added_countries = 0
    added_features = 0
    for iso, features in sorted(grouped.items()):
        if not features:
            continue
        first_props = features[0].get("properties") or {}
        record = {
            "boundaryISO": iso,
            "boundaryName": str(first_props.get("NAM_0") or iso),
            "boundaryYearRepresented": WB_UPDATED,
            "boundaryID": f"WB-GAD-{WB_UPDATED}-{iso}-{level}",
            "boundarySource": "World Bank Official Boundaries (WB-GAD)",
            "boundarySourceURL": WB_CATALOG_URL,
            "boundaryLicense": "CC BY 4.0",
            "licenseDetail": "World Bank Official Boundaries dataset, Creative Commons Attribution 4.0; attribution required.",
            "licenseSource": WB_CATALOG_URL,
            "Continent": "Unknown",
            "source_version": f"World Bank Official Boundaries; catalog updated {WB_UPDATED}",
            "boundary_product": "World Bank Official Boundaries fallback",
            "geometry_detail": "World Bank ArcGIS FeatureServer query, EPSG:4326",
            "is_global_composite_fallback": True,
        }
        source = {"type": "FeatureCollection", "features": features}
        prepared = validate_and_prepare(record, level, source)
        path = OUTPUT / f"{iso}_{level}.geojson"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(prepared, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        metadata = prepared["metadata"]
        packages[iso] = {
            "file": f"boundaries/global/{iso}_{level}.geojson",
            "feature_count": metadata["feature_count"],
            "boundary_id": metadata["boundary_id"],
            "boundary_year": metadata["boundary_year"],
            "country_name": metadata["country_name"],
            "source": metadata["source"],
            "source_url": metadata["source_url"],
            "license": metadata["license"],
            "license_detail": metadata["license_detail"],
            "license_source": metadata["license_source"],
            "continent": metadata["continent"],
            "geometry_detail": metadata["geometry_detail"],
            "boundary_product": metadata["boundary_product"],
            "is_global_composite_fallback": True,
        }
        added_countries += 1
        added_features += metadata["feature_count"]

    print(
        f"PASS WORLD BANK FALLBACK {level}: added {added_countries} countries / "
        f"{added_features:,} polygons"
    )
    return {"country_count": added_countries, "feature_count": added_features}


async def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    old_manifest = read_json(OUTPUT / "manifest.json")
    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(180.0, connect=30.0),
        follow_redirects=True,
        limits=httpx.Limits(max_connections=MAX_CONCURRENCY * 2),
    ) as client:
        level_results = {}
        failures = []
        for level in LEVELS:
            packages, level_failures = await build_level(client, level, semaphore, old_manifest)
            level_results[level] = packages
            failures.extend(level_failures)

        world_bank_fallback_summary = {}
        for level in LEVELS:
            try:
                world_bank_fallback_summary[level] = await add_world_bank_fallback(
                    client, level, level_results[level], semaphore
                )
            except Exception as exc:
                print(f"WARN WORLD BANK FALLBACK {level}: service query unavailable; retaining validated gbOpen packages: {exc}")
                world_bank_fallback_summary[level] = {"country_count": 0, "feature_count": 0, "error": str(exc)}

    countries: dict[str, dict] = {}
    for level, packages in level_results.items():
        for iso, metadata in packages.items():
            country = countries.setdefault(
                iso,
                {
                    "name": metadata.get("country_name") or iso,
                    "continent": metadata.get("continent") or "Unknown",
                    "levels": {},
                },
            )
            country["levels"][level] = metadata

    total_bytes = sum(path.stat().st_size for path in OUTPUT.glob("*.geojson"))
    if total_bytes > MAX_TOTAL_BYTES:
        raise RuntimeError(
            f"Global static package is {total_bytes / 1024 / 1024:.1f} MB; "
            f"configured safety ceiling is {MAX_TOTAL_BYTES / 1024 / 1024:.0f} MB"
        )
    manifest = {
        "dataset": "geoBoundaries gbOpen + World Bank fallback",
        "api": API_BASE,
        "source_url": "https://www.geoboundaries.org/",
        "api_documentation": "https://geoboundaries-dev.org/api",
        "release_type": "gbOpen with World Bank fallback",
        "world_bank_fallback": {
            "name": "World Bank Official Boundaries (WB-GAD)",
            "source_url": WB_CATALOG_URL,
            "service_url": WB_ARCGIS_BASE,
            "license": "CC BY 4.0",
            "catalog_updated": WB_UPDATED,
            "added_by_level": world_bank_fallback_summary,
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "delivery": "GitHub Pages static per-country GeoJSON; browser downloads only the selected country and level",
        "uzb_policy": "UZB retains the separately validated ADM1/ADM2 snapshot used by the public MAPSPAM shapeID join",
        "coverage_note": (
            "Country-specific gbOpen boundaries are preferred. Missing country/level packages "
            "are supplemented from the World Bank Official Boundaries (WB-GAD) service. Boundary "
            "vintage and license are retained per country; a level is unavailable only if neither "
            "source provides it."
        ),
        "attribution": (
            "geoBoundaries, William & Mary geoLab, World Bank and upstream contributors. "
            "Retain each file's boundary source, license and license-source metadata."
        ),
        "level_summary": {
            level: {
                "country_count": len(packages),
                "feature_count": sum(int(row.get("feature_count", 0)) for row in packages.values()),
            }
            for level, packages in level_results.items()
        },
        "package_bytes": total_bytes,
        "refresh_failures_using_cache": failures,
        "countries": dict(sorted(countries.items())),
    }
    (OUTPUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        "PASS global boundary package: "
        + ", ".join(
            f"{level}={summary['country_count']} countries / {summary['feature_count']:,} polygons"
            for level, summary in manifest["level_summary"].items()
        )
        + f" | {total_bytes / 1024 / 1024:.1f} MB"
    )
    if failures:
        print(f"WARN: {len(failures)} country-level source refreshes used no cache and are unavailable")
        for failure in failures[:20]:
            print("WARN:", failure)


if __name__ == "__main__":
    asyncio.run(main())
