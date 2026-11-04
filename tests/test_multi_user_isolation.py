import os
import uuid

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///./tests/osh_agri_sqlite_test.sqlite3")
os.environ.setdefault("ENABLE_POSTGIS", "false")
os.environ.setdefault("JWT_SECRET", "multiuser-isolation-test-secret-not-production")

from fastapi.testclient import TestClient
from backend.app.main import app


def register(client, email):
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "multiuser-test-password-123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def polygon():
    return {
        "type": "Polygon",
        "coordinates": [[
            [69.1, 41.2], [69.3, 41.2], [69.3, 41.4],
            [69.1, 41.4], [69.1, 41.2],
        ]],
    }


def test_users_cannot_read_or_analyze_each_others_locations_or_jobs():
    with TestClient(app) as client:
        user_a = register(client, f"a-{uuid.uuid4().hex}@example.test")
        user_b = register(client, f"b-{uuid.uuid4().hex}@example.test")

        saved = client.post(
            "/api/v1/locations",
            headers=user_a,
            json={
                "country_iso3": "UZB",
                "name": "Private A region",
                "admin_level": "ADM1",
                "climate_start_year": 2022,
                "geojson": polygon(),
            },
        )
        assert saved.status_code == 200, saved.text
        location_id = saved.json()["id"]
        climate_job_id = saved.json()["climate_job_id"]

        # Owner can see own location and job.
        own_locations = client.get("/api/v1/locations", headers=user_a)
        assert own_locations.status_code == 200
        assert any(x["id"] == location_id for x in own_locations.json())
        own_job = client.get(
            f"/api/v1/location-climate-jobs/{climate_job_id}", headers=user_a
        )
        assert own_job.status_code == 200

        # Other users cannot list or fetch the private location/job.
        other_locations = client.get("/api/v1/locations", headers=user_b)
        assert other_locations.status_code == 200
        assert all(x["id"] != location_id for x in other_locations.json())

        hidden_climate = client.get(
            f"/api/v1/locations/{location_id}/climate", headers=user_b
        )
        assert hidden_climate.status_code == 404

        hidden_job = client.get(
            f"/api/v1/location-climate-jobs/{climate_job_id}", headers=user_b
        )
        assert hidden_job.status_code == 404

        cannot_requeue = client.post(
            f"/api/v1/locations/{location_id}/analyze", headers=user_b
        )
        assert cannot_requeue.status_code == 404

        # User B cannot attach a CSV to User A's private location.
        upload = client.post(
            "/api/v1/datasets/upload",
            headers=user_b,
            data={"location_id": str(location_id), "crop_code": "WHEAT"},
            files={"file": ("yield.csv", "year,yield_t_ha\n2020,3.1\n", "text/csv")},
        )
        assert upload.status_code == 404
