import httpx
from fastapi import HTTPException
from ..config import settings

VALID_LEVELS={f"ADM{i}" for i in range(6)}

async def get_boundary_geojson(iso3:str,level:str)->dict:
    iso3=iso3.upper().strip()
    level=level.upper().strip()
    if len(iso3)!=3 or not iso3.isalpha():
        raise HTTPException(400,"ISO-3 noto‘g‘ri")
    if level not in VALID_LEVELS:
        raise HTTPException(400,"ADM0–ADM5 oralig‘i kerak")
    errors=[]
    async with httpx.AsyncClient(timeout=60,follow_redirects=True) as client:
        for source in ("gbOpen","gbHumanitarian"):
            url=f"https://www.geoboundaries.org/api/current/{source}/{iso3}/{level}/"
            try:
                response=await client.get(url)
                if response.status_code==404:
                    continue
                response.raise_for_status()
                meta=response.json()
                geo_url=meta.get("gjDownloadURL") or meta.get("simplifiedGeometryGeoJSON")
                if not geo_url:
                    continue
                geo_response=await client.get(geo_url)
                geo_response.raise_for_status()
                geo=geo_response.json()
                if geo.get("type")!="FeatureCollection" or not geo.get("features"):
                    continue
                return {"type":"FeatureCollection","features":geo["features"],"metadata":{
                    "country_iso3":iso3,"admin_level":level,"source":f"geoBoundaries {source}",
                    "source_url":url,"license":meta.get("license","Review source metadata"),
                    "boundary_year":meta.get("boundaryYearRepresented"),
                    "fallback_used":source!="gbOpen"
                }}
            except Exception as exc:
                errors.append(f"{source}: {exc}")
    raise HTTPException(404,f"{iso3} uchun {level} chegarasi topilmadi. {'; '.join(errors)[:400]}")
