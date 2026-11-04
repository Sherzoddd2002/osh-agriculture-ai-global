import os
import uuid

# Ensure the app is imported against an isolated SQLite database for this test.
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///./tests/osh_agri_sqlite_test.sqlite3")
os.environ.setdefault("ENABLE_POSTGIS", "false")
os.environ.setdefault("JWT_SECRET", "sqlite-integration-test-secret-not-for-production")

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.main import app
from backend.app.db import SessionLocal
from backend.app.models import Location


def test_sqlite_api_registration_location_and_dataset_flow():
    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        assert health.status_code == 200
        assert health.json()["ok"] is True
        assert health.json()["database"] == "connected"

        email = f"sqlite-test-{uuid.uuid4().hex}@example.test"
        registration = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "test-password-123"},
        )
        assert registration.status_code == 200
        token = registration.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        location_response = client.post(
            "/api/v1/locations",
            headers=headers,
            json={
                "country_iso3": "UZB",
                "name": "Test polygon",
                "admin_level": "ADM1",
                "geojson": {
                    "type": "Polygon",
                    "coordinates": [[
                        [69.1, 41.2],
                        [69.3, 41.2],
                        [69.3, 41.4],
                        [69.1, 41.4],
                        [69.1, 41.2],
                    ]],
                },
            },
        )
        assert location_response.status_code == 200, location_response.text
        location_id = location_response.json()["id"]

        # Verify that GeoJSON is persisted in SQLite JSON, without PostGIS.
        with SessionLocal() as db:
            saved = db.scalar(select(Location).where(Location.id == location_id))
            assert saved is not None
            assert saved.geojson["type"] == "Polygon"
            assert saved.centroid_lat > 0
            assert saved.centroid_lon > 0

        csv_data = "year,yield_t_ha\\n2020,3.1\\n2021,3.3\\n2022,3.4\\n"
        upload = client.post(
            "/api/v1/datasets/upload",
            headers=headers,
            data={"location_id": str(location_id), "crop_code": "WHEAT"},
            files={"file": ("wheat.csv", csv_data, "text/csv")},
        )
        assert upload.status_code == 200, upload.text
        dataset_id = upload.json()["dataset_id"]
        assert upload.json()["row_count"] == 3

        queued = client.post(
            f"/api/v1/datasets/{dataset_id}/process",
            headers=headers,
        )
        assert queued.status_code == 200, queued.text
        assert queued.json()["status"] == "QUEUED"
