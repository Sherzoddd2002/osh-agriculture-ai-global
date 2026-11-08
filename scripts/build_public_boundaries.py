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


async def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest = {
        "country_iso3": "UZB",
        "country_name": "Uzbekistan",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "delivery": "GitHub Pages static GeoJSON; no runtime API required",
        "levels": {},
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
