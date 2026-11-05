import asyncio

import httpx
import pytest
from fastapi import HTTPException

from backend.app.services import boundaries


FEATURE_COLLECTION = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {"shapeName": "Tashkent"},
            "geometry": {
                "type": "Polygon",
                "coordinates": [[
                    [69.0, 41.0], [70.0, 41.0], [70.0, 42.0],
                    [69.0, 42.0], [69.0, 41.0],
                ]],
            },
        }
    ],
}


class FakeResponse:
    def __init__(self, url, status_code, payload=None):
        self.request = httpx.Request("GET", url)
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            response = httpx.Response(self.status_code, request=self.request)
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=self.request,
                response=response,
            )


class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.responses = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, **kwargs):
        self.responses.append(url)
        if "geoboundaries.org/api/current/gbOpen/" in url:
            return FakeResponse(url, 404)
        if "geoboundaries.org/api/current/gbHumanitarian/" in url:
            return FakeResponse(url, 404)
        if "github.com/wmgeolab/geoBoundaries/raw/" in url:
            return FakeResponse(url, 200, FEATURE_COLLECTION)
        return FakeResponse(url, 404)


def test_uzb_adm1_uses_official_github_fallback(monkeypatch):
    monkeypatch.setattr(boundaries.httpx, "AsyncClient", FakeAsyncClient)

    result = asyncio.run(boundaries.get_boundary_geojson("uzb", "adm1"))

    assert result["type"] == "FeatureCollection"
    assert len(result["features"]) == 1
    assert result["features"][0]["properties"]["shapeName"] == "Tashkent"
    assert result["metadata"]["country_iso3"] == "UZB"
    assert result["metadata"]["admin_level"] == "ADM1"
    assert result["metadata"]["fallback_used"] is True
    assert "GitHub" in result["metadata"]["source"]


def test_invalid_boundary_level_is_rejected():
    with pytest.raises(HTTPException) as exc:
        asyncio.run(boundaries.get_boundary_geojson("UZB", "ADM9"))
    assert exc.value.status_code == 400


def test_boundary_geojson_with_no_polygon_is_rejected(monkeypatch):
    class InvalidBoundaryClient(FakeAsyncClient):
        async def get(self, url, **kwargs):
            if "geoboundaries.org/api/current/" in url:
                return FakeResponse(url, 404)
            if "github.com/wmgeolab/geoBoundaries/raw/" in url:
                return FakeResponse(
                    url,
                    200,
                    {"type": "FeatureCollection", "features": []},
                )
            return FakeResponse(url, 404)

    monkeypatch.setattr(boundaries.httpx, "AsyncClient", InvalidBoundaryClient)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(boundaries.get_boundary_geojson("UZB", "ADM1"))
    assert exc.value.status_code == 404
    assert "FeatureCollection" in exc.value.detail
