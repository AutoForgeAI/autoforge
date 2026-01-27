"""Lightweight tests for the /health endpoint."""

from fastapi.testclient import TestClient

from server.main import app


client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json().get("status") == "ok"
