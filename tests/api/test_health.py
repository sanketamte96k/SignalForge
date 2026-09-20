"""Tests for SignalForge API health routes."""

from fastapi.testclient import TestClient

from src.api.main import app


client = TestClient(app)


def test_root_endpoint() -> None:
    """Root endpoint should report a healthy API."""

    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "SignalForge API",
        "status": "ok",
        "version": "0.1.0",
    }


def test_health_endpoint() -> None:
    """Health endpoint should return the expected response."""

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "SignalForge API",
    }
