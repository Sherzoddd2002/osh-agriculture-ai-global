import asyncio

import httpx

from backend.app import main as api


def test_boundary_api_route_returns_geojson(monkeypatch):
    async def fake_boundary(iso3: str, admin_level: str):
        assert iso3 == "uzb"
        assert admin_level == "adm1"
        return {
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
            "metadata": {"country_iso3": "UZB", "admin_level": "ADM1"},
        }

    monkeypatch.setattr(api, "get_boundary_geojson", fake_boundary)

    async def request():
        transport = httpx.ASGITransport(app=api.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get("/api/v1/boundaries/uzb/adm1")

    response = asyncio.run(request())

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert payload["metadata"] == {
        "country_iso3": "UZB",
        "admin_level": "ADM1",
    }
    assert payload["features"][0]["properties"]["shapeName"] == "Tashkent"
