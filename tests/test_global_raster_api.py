import os

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///./tests/osh_agri_sqlite_test.sqlite3")
os.environ.setdefault("ENABLE_POSTGIS", "false")
os.environ.setdefault("JWT_SECRET", "sqlite-integration-test-secret-not-for-production")

from fastapi.testclient import TestClient

from backend.app.main import app


POLYGON = {
    "type": "Polygon",
    "coordinates": [[
        [60.0, 40.0], [61.0, 40.0], [61.0, 41.0],
        [60.0, 41.0], [60.0, 40.0],
    ]],
}


def test_global_raster_catalog_and_download_status_are_public():
    with TestClient(app) as client:
        catalog = client.get("/api/v1/global-raster-catalog")
        assert catalog.status_code == 200
        assert catalog.json()["mapspam"]["crop_count"] == 46
        assert catalog.json()["cropgrids"]["crop_count"] == 173
        assert catalog.json()["mapspam"]["variables"]["production"]["unit"] == "t"

        status = client.get("/api/v1/global-raster-status")
        assert status.status_code == 200
        assert "mapspam" in status.json()
        assert "cropgrids" in status.json()


def test_custom_aoi_mapspam_summary_is_public_and_reports_missing_assets(monkeypatch, tmp_path):
    payload = {
        "geojson": POLYGON,
        "crop_code": "whea",
        "technology": "all",
        "location_name": "Test field",
        "admin_level": "CUSTOM",
    }
    monkeypatch.setenv("OSH_AGRI_DATA_DIR", str(tmp_path))

    with TestClient(app) as client:
        # A drawn field is a public, read-only zonal query against open MAPSPAM
        # data. It must not require account creation or a JWT.
        missing_assets = client.post(
            "/api/v1/global-raster-summary/mapspam", json=payload
        )
        assert missing_assets.status_code == 503
        assert "not fully synced" in missing_assets.json()["detail"]

        unknown_crop = {**payload, "crop_code": "xxxx"}
        invalid = client.post(
            "/api/v1/global-raster-summary/mapspam", json=unknown_crop
        )
        assert invalid.status_code == 422

        wide_polygon = {
            **payload,
            "geojson": {
                "type": "Polygon",
                "coordinates": [[
                    [60.0, 40.0], [63.0, 40.0], [63.0, 41.0],
                    [60.0, 41.0], [60.0, 40.0],
                ]],
            },
        }
        bounded = client.post(
            "/api/v1/global-raster-summary/mapspam", json=wide_polygon
        )
        assert bounded.status_code == 413
        assert "2.5 degrees" in bounded.json()["detail"]
