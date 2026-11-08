"""Live smoke test for Uzbekistan ADM1 and ADM2 geoBoundaries.

This makes real outbound requests and verifies that both administrative levels
return non-empty, valid Polygon/MultiPolygon GeoJSON rather than HTML or an
unresolved Git LFS pointer.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from shapely.geometry import shape

from backend.app.services.boundaries import get_boundary_geojson


async def verify_level(level: str) -> dict:
    result = await get_boundary_geojson("UZB", level)
    if result.get("type") != "FeatureCollection":
        raise SystemExit(f"FAIL: UZB {level} response is not a FeatureCollection")

    features = result.get("features")
    if not isinstance(features, list) or not features:
        raise SystemExit(f"FAIL: UZB {level} returned no features")

    polygon_count = 0
    for feature in features:
        geometry = feature.get("geometry") if isinstance(feature, dict) else None
        if not geometry:
            continue
        parsed = shape(geometry)
        if (
            not parsed.is_empty
            and parsed.is_valid
            and parsed.geom_type in {"Polygon", "MultiPolygon"}
        ):
            polygon_count += 1

    metadata = result.get("metadata") or {}
    if polygon_count == 0:
        raise SystemExit(f"FAIL: UZB {level} has no valid Polygon/MultiPolygon")
    if metadata.get("country_iso3") != "UZB":
        raise SystemExit(f"FAIL: unexpected {level} country metadata: {metadata!r}")
    if metadata.get("admin_level") != level:
        raise SystemExit(f"FAIL: unexpected {level} metadata: {metadata!r}")

    return {
        "status": "PASS",
        "country_iso3": "UZB",
        "admin_level": level,
        "feature_count": len(features),
        "valid_polygon_count": polygon_count,
        "source": metadata.get("source"),
        "boundary_year": metadata.get("boundary_year"),
        "license": metadata.get("license"),
        "fallback_used": metadata.get("fallback_used"),
        "source_url": metadata.get("source_url"),
    }


async def main() -> None:
    results = [await verify_level(level) for level in ("ADM1", "ADM2")]
    print(json.dumps({"status": "PASS", "boundaries": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
