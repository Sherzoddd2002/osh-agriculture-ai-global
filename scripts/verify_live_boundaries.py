"""Live smoke test for the official geoBoundaries UZB ADM1 source path.

This deliberately makes a real outbound request. It is used in CI to ensure
that metadata lookup or the official GitHub LFS-backed fallback returns actual
Polygon/MultiPolygon GeoJSON, not an HTML page or a Git LFS pointer.
"""
from __future__ import annotations

import asyncio
import json

from shapely.geometry import shape

from backend.app.services.boundaries import get_boundary_geojson


async def main() -> None:
    result = await get_boundary_geojson("UZB", "ADM1")
    if result.get("type") != "FeatureCollection":
        raise SystemExit("FAIL: boundary response is not a FeatureCollection")

    features = result.get("features")
    if not isinstance(features, list) or not features:
        raise SystemExit("FAIL: UZB ADM1 returned no features")

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
        raise SystemExit("FAIL: no valid Polygon/MultiPolygon geometries")

    if metadata.get("country_iso3") != "UZB":
        raise SystemExit(f"FAIL: unexpected country metadata: {metadata!r}")
    if metadata.get("admin_level") != "ADM1":
        raise SystemExit(f"FAIL: unexpected admin level metadata: {metadata!r}")

    print(json.dumps({
        "status": "PASS",
        "country_iso3": "UZB",
        "admin_level": "ADM1",
        "feature_count": len(features),
        "valid_polygon_count": polygon_count,
        "source": metadata.get("source"),
        "fallback_used": metadata.get("fallback_used"),
        "source_url": metadata.get("source_url"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
