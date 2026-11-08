"""Copernicus Data Space STAC discovery for Sentinel-2 L2A scenes.

This module searches catalogue metadata only. It does not claim to have computed
NDVI until a raster-processing job downloads/reads B04, B08 and SCL/CLD pixels,
applies masks, and aggregates valid pixels over the saved AOI.
"""
from __future__ import annotations

from datetime import date
import httpx


STAC_SEARCH_URL = "https://stac.dataspace.copernicus.eu/v1/search"
COLLECTION = "sentinel-2-l2a"


async def search_sentinel2_scenes(
    geometry: dict,
    start_date: date,
    end_date: date,
    max_cloud_percent: float = 30.0,
    limit: int = 50,
) -> dict:
    if end_date < start_date:
        raise ValueError("end_date start_date dan oldin bo‘lishi mumkin emas")
    if not 0 <= max_cloud_percent <= 100:
        raise ValueError("max_cloud_percent 0–100 oralig‘ida bo‘lishi kerak")
    if not 1 <= limit <= 100:
        raise ValueError("limit 1–100 oralig‘ida bo‘lishi kerak")
    if not isinstance(geometry, dict) or geometry.get("type") not in {"Polygon", "MultiPolygon"}:
        raise ValueError("Sentinel-2 qidiruvi uchun Polygon yoki MultiPolygon AOI talab qilinadi")

    payload = {
        "collections": [COLLECTION],
        "intersects": geometry,
        "datetime": (
            f"{start_date.isoformat()}T00:00:00Z/"
            f"{end_date.isoformat()}T23:59:59Z"
        ),
        "limit": limit,
        "query": {"eo:cloud_cover": {"lte": float(max_cloud_percent)}},
    }
    async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
        response = await client.post(
            STAC_SEARCH_URL,
            json=payload,
            headers={"Accept": "application/geo+json", "Content-Type": "application/json"},
        )
        response.raise_for_status()
        document = response.json()

    items = []
    for item in document.get("features", []):
        properties = item.get("properties") or {}
        assets = item.get("assets") or {}
        selected_assets = {}
        for key, asset in assets.items():
            normalised = key.lower()
            if normalised in {"b04", "b08", "scl", "cld", "data-mask", "datamask"}:
                selected_assets[key] = {
                    "href": asset.get("href"),
                    "type": asset.get("type"),
                    "roles": asset.get("roles") or [],
                }
        items.append({
            "id": item.get("id"),
            "datetime": properties.get("datetime"),
            "cloud_cover_percent": properties.get("eo:cloud_cover"),
            "platform": properties.get("platform"),
            "instrument": properties.get("instruments"),
            "assets_available": sorted(selected_assets.keys()),
            "assets": selected_assets,
        })

    return {
        "source": "Copernicus Data Space Ecosystem STAC",
        "endpoint": STAC_SEARCH_URL,
        "collection": COLLECTION,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "max_cloud_percent": float(max_cloud_percent),
        "returned": len(items),
        "items": items,
        "catalogue_only": True,
        "ndvi_status": "NOT_COMPUTED",
        "next_page_available": any(
            link.get("rel") == "next" for link in (document.get("links") or [])
        ),
        "note": (
            "Bu natija faqat Sentinel-2 L2A sahnalari katalogini topadi. NDVI uchun "
            "B08/B04 rasterlarini olish, SCL/CLD cloud-shadow mask qo‘llash, "
            "valid pixel soni va AOI bo‘yicha median/mean statistikani hisoblash kerak."
        ),
    }
