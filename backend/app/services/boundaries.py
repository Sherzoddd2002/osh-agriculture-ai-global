from __future__ import annotations

import httpx
from fastapi import HTTPException
from shapely.geometry import shape

VALID_LEVELS = {f"ADM{i}" for i in range(6)}


def _validate_feature_collection(payload: object) -> dict:
    if (
        not isinstance(payload, dict)
        or payload.get("type") != "FeatureCollection"
        or not isinstance(payload.get("features"), list)
        or not payload["features"]
    ):
        raise ValueError("Boundary non-empty GeoJSON FeatureCollection emas")

    polygon_count = 0
    for feature in payload["features"]:
        if not isinstance(feature, dict) or not feature.get("geometry"):
            continue
        geometry = shape(feature["geometry"])
        if (
            not geometry.is_empty
            and geometry.is_valid
            and geometry.geom_type in {"Polygon", "MultiPolygon"}
        ):
            polygon_count += 1

    if polygon_count == 0:
        raise ValueError("Boundary ichida yaroqli Polygon/MultiPolygon topilmadi")
    return payload


def _response_payload(iso3: str, level: str, metadata: dict, geojson: dict, source: str, source_url: str, fallback: bool) -> dict:
    return {
        "type": "FeatureCollection",
        "features": geojson["features"],
        "metadata": {
            "country_iso3": iso3,
            "admin_level": level,
            "source": source,
            "source_url": source_url,
            "license": (
                metadata.get("boundaryLicense")
                or metadata.get("license")
                or "Check source release metadata"
            ),
            "boundary_year": metadata.get("boundaryYearRepresented"),
            "boundary_id": metadata.get("boundaryID"),
            "boundary_name": metadata.get("boundaryName"),
            "boundary_canonical": metadata.get("boundaryCanonical"),
            "fallback_used": fallback,
        },
    }


async def get_boundary_geojson(iso3: str, level: str) -> dict:
    iso3 = iso3.upper().strip()
    level = level.upper().strip()
    if len(iso3) != 3 or not iso3.isalpha():
        raise HTTPException(400, "ISO-3 noto‘g‘ri")
    if level not in VALID_LEVELS:
        raise HTTPException(400, "ADM0–ADM5 oralig‘i kerak")

    errors: list[str] = []
    async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
        # 1. Preferred official geoBoundaries metadata API.
        for source in ("gbOpen", "gbHumanitarian"):
            url = f"https://www.geoboundaries.org/api/current/{source}/{iso3}/{level}/"
            try:
                response = await client.get(url)
                if response.status_code == 404:
                    errors.append(f"{source} metadata: HTTP 404")
                    continue
                response.raise_for_status()
                metadata = response.json()
                download_urls = []
                for candidate in (
                    metadata.get("simplifiedGeometryGeoJSON"),
                    metadata.get("gjDownloadURL"),
                ):
                    if candidate and candidate not in download_urls:
                        download_urls.append(candidate)

                if not download_urls:
                    errors.append(f"{source}: metadata GeoJSON URL bermadi")
                    continue

                for download_url in download_urls:
                    try:
                        geo_response = await client.get(download_url)
                        geo_response.raise_for_status()
                        geojson = _validate_feature_collection(geo_response.json())
                        return _response_payload(
                            iso3, level, metadata, geojson,
                            f"geoBoundaries {source}", url, fallback=(source != "gbOpen"),
                        )
                    except Exception as exc:
                        errors.append(f"{source} GeoJSON: {exc}")
            except Exception as exc:
                errors.append(f"{source} metadata: {exc}")

        # 2. Official geoBoundaries GitHub release archive fallback.
        # github.com/raw resolves Git LFS objects; raw.githubusercontent.com
        # may return only the small Git LFS pointer document.
        github_base = (
            "https://github.com/wmgeolab/geoBoundaries/raw/refs/heads/main/"
            f"releaseData/gbOpen/{iso3}/{level}/"
        )
        for filename in (
            f"geoBoundaries-{iso3}-{level}_simplified.geojson",
            f"geoBoundaries-{iso3}-{level}.geojson",
        ):
            github_url = github_base + filename
            try:
                response = await client.get(github_url)
                if response.status_code == 404:
                    errors.append(f"GitHub {filename}: HTTP 404")
                    continue
                response.raise_for_status()
                geojson = _validate_feature_collection(response.json())
                metadata = {
                    "boundaryID": f"gbOpen-{iso3}-{level}",
                    "boundaryYearRepresented": None,
                    "boundaryName": iso3,
                    "boundaryLicense": "See official geoBoundaries release metadata",
                }
                return _response_payload(
                    iso3, level, metadata, geojson,
                    "official geoBoundaries GitHub gbOpen release",
                    github_url, fallback=True,
                )
            except Exception as exc:
                errors.append(f"GitHub {filename}: {exc}")

    detail = "; ".join(errors)[:1000] or "Boundary source returned no data"
    raise HTTPException(
        404,
        f"{iso3} uchun {level} chegarasi topilmadi. Manba xatolari: {detail}",
    )
