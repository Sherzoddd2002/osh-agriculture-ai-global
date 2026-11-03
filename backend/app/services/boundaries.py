import httpx
from fastapi import HTTPException
from ..config import settings

VALID_LEVELS = {f"ADM{i}" for i in range(6)}


async def get_boundary_geojson(iso3: str, level: str) -> dict:
    iso3 = iso3.upper().strip()
    level = level.upper().strip()
    if len(iso3) != 3 or not iso3.isalpha():
        raise HTTPException(400, "Mamlakat ISO-3 kodi 3 ta lotin harfidan iborat bo‘lishi kerak")
    if level not in VALID_LEVELS:
        raise HTTPException(400, "Ma’muriy daraja ADM0–ADM5 oralig‘ida bo‘lishi kerak")
    url = f"{settings.geboundaries_base_url}/{iso3}/{level}/"
    try:
        async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
            meta_response = await client.get(url)
            if meta_response.status_code == 404:
                raise HTTPException(404, f"{iso3} uchun {level} chegarasi topilmadi")
            meta_response.raise_for_status()
            meta = meta_response.json()
            geo_url = meta.get("gjDownloadURL") or meta.get("simplifiedGeometryGeoJSON")
            if not geo_url:
                raise HTTPException(404, "Chegara GeoJSON manzili mavjud emas")
            geo_response = await client.get(geo_url)
            geo_response.raise_for_status()
            geo = geo_response.json()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f"geoBoundaries manbasiga ulanib bo‘lmadi: {exc}")
    if geo.get("type") != "FeatureCollection":
        raise HTTPException(502, "GeoJSON javobi FeatureCollection emas")
    return {
        "type": "FeatureCollection",
        "features": geo.get("features", []),
        "metadata": {
            "country_iso3": iso3,
            "admin_level": level,
            "source": "geoBoundaries gbOpen",
            "source_url": url,
            "license": meta.get("license", "Metadata may vary; review the returned boundary metadata"),
            "boundary_year": meta.get("boundaryYearRepresented"),
            "attribution": "geoBoundaries; CC BY 4.0 / ODbL terms can vary by boundary. Review source metadata.",
        },
    }
