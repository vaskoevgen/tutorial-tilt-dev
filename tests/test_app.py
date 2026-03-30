"""
Integration tests for the tutorial app.
Run these with Tilt's local_resource or manually:
  pytest tests/ -v
Requires APP_URL env var (default: http://localhost:8000).
"""
import os
import pytest
import httpx

BASE_URL = os.getenv("APP_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=BASE_URL, timeout=10) as c:
        yield c


# ── Test cases ────────────────────────────────────────────────────────────────

class TestHealth:
    def test_root_returns_ok(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_health_endpoint_reports_healthy(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "healthy"
        assert body["redis"] == "connected"


class TestCounter:
    def test_reset_then_get_returns_zero(self, client):
        client.post("/count/reset")
        r = client.get("/count")
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_increment_increases_by_one(self, client):
        client.post("/count/reset")
        r = client.post("/count/increment")
        assert r.status_code == 200
        assert r.json()["count"] == 1

    def test_multiple_increments_accumulate(self, client):
        client.post("/count/reset")
        for _ in range(5):
            client.post("/count/increment")
        r = client.get("/count")
        assert r.json()["count"] == 5

    def test_reset_clears_accumulated_count(self, client):
        for _ in range(3):
            client.post("/count/increment")
        r = client.post("/count/reset")
        assert r.json()["count"] == 0
        r = client.get("/count")
        assert r.json()["count"] == 0
