from datetime import date
import asyncio

import pytest

from backend.app.services import sentinel2


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeAsyncClient:
    def __init__(self, payload, **kwargs):
        self.payload = payload
        self.request = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, *, json, headers):
        self.request = {"url": url, "json": json, "headers": headers}
        return FakeResponse(self.payload)


def test_sentinel2_rejects_invalid_geometry_without_network():
    with pytest.raises(ValueError, match="Polygon yoki MultiPolygon"):
        asyncio.run(
            sentinel2.search_sentinel2_scenes(
                geometry={"type": "Point", "coordinates": [69.2, 41.3]},
                start_date=date(2025, 4, 1),
                end_date=date(2025, 5, 1),
            )
        )


def test_sentinel2_rejects_invalid_cloud_limit_without_network():
    polygon = {
        "type": "Polygon",
        "coordinates": [[[69.0, 41.0], [69.1, 41.0], [69.1, 41.1], [69.0, 41.0]]],
    }
    with pytest.raises(ValueError, match="0–100"):
        asyncio.run(
            sentinel2.search_sentinel2_scenes(
                geometry=polygon,
                start_date=date(2025, 4, 1),
                end_date=date(2025, 5, 1),
                max_cloud_percent=101,
            )
        )


def test_sentinel2_posts_aoi_date_and_cloud_filter_and_returns_assets(monkeypatch):
    polygon = {
        "type": "Polygon",
        "coordinates": [[[69.0, 41.0], [69.1, 41.0], [69.1, 41.1], [69.0, 41.0]]],
    }
    payload = {
        "features": [
            {
                "id": "S2A_TEST_SCENE",
                "properties": {
                    "datetime": "2025-04-15T06:30:00Z",
                    "eo:cloud_cover": 7.5,
                    "platform": "sentinel-2a",
                    "instruments": ["msi"],
                },
                "assets": {
                    "B04_10m": {"href": "https://example.test/red.tif", "type": "image/tiff"},
                    "B08_10m": {"href": "https://example.test/nir.tif", "type": "image/tiff"},
                    "SCL_20m": {"href": "https://example.test/scl.tif", "type": "image/tiff"},
                    "thumbnail": {"href": "https://example.test/preview.jpg", "type": "image/jpeg"},
                },
            }
        ],
        "links": [{"rel": "next", "href": "https://example.test/next"}],
    }
    fake_client = FakeAsyncClient(payload)
    monkeypatch.setattr(
        sentinel2.httpx,
        "AsyncClient",
        lambda **kwargs: fake_client,
    )

    result = asyncio.run(
        sentinel2.search_sentinel2_scenes(
            geometry=polygon,
            start_date=date(2025, 4, 1),
            end_date=date(2025, 4, 30),
            max_cloud_percent=20,
            limit=25,
        )
    )

    assert fake_client.request["url"] == sentinel2.STAC_SEARCH_URL
    assert fake_client.request["json"]["collections"] == ["sentinel-2-l2a"]
    assert fake_client.request["json"]["intersects"] == polygon
    assert fake_client.request["json"]["query"]["eo:cloud_cover"]["lte"] == 20.0
    assert result["returned"] == 1
    assert result["items"][0]["assets_available"] == ["B04_10m", "B08_10m", "SCL_20m"]
    assert result["catalogue_only"] is True
    assert result["ndvi_status"] == "NOT_COMPUTED"
    assert result["next_page_available"] is True


def test_environment_registry_does_not_claim_unimplemented_rasters_are_active():
    from backend.app.services.connectors import SOURCE_REGISTRY

    assert SOURCE_REGISTRY["SENTINEL2_NDVI"]["status"] == "CATALOG_AVAILABLE"
    assert SOURCE_REGISTRY["NASA_SMAP"]["status"] == "DATASET_AVAILABLE_AUTH_REQUIRED"
    assert SOURCE_REGISTRY["SOILGRIDS"]["status"] == "WCS_AVAILABLE_REST_PAUSED"
