"""
Tests for feature test evidence (issue #69).

Covers recording evidence through the feature MCP tools and reading it back
through the features REST API, including screenshot path restrictions.

Run with: python -m pytest test_feature_evidence.py
"""

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import mcp_server.feature_mcp as feature_mcp
from api.database import Feature, create_database
from server.routers import features as features_router


@pytest.fixture
def project(tmp_path, monkeypatch):
    """Initialize a project database and point the MCP module at it."""
    project_dir = tmp_path.resolve()
    monkeypatch.setattr(feature_mcp, "PROJECT_DIR", project_dir)
    monkeypatch.setattr(feature_mcp, "AGENT_TYPE", "testing")
    engine, session_maker = create_database(project_dir)
    monkeypatch.setattr(feature_mcp, "_engine", engine)
    monkeypatch.setattr(feature_mcp, "_session_maker", session_maker)
    created = json.loads(feature_mcp.feature_create(
        category="auth", name="Login", description="User can log in", steps=["Open /login"],
    ))
    assert created["success"]
    yield project_dir
    engine.dispose()


@pytest.fixture
def client(project, monkeypatch):
    monkeypatch.setattr(features_router, "_get_project_path", lambda name: project)
    app = FastAPI()
    app.include_router(features_router.router)
    return TestClient(app)


def _evidence(project_dir):
    session = feature_mcp.get_session()
    try:
        return session.get(Feature, 1).test_evidence
    finally:
        session.close()


def test_mark_passing_records_evidence(project):
    shot = project / ".playwright-cli" / "login.png"
    shot.parent.mkdir()
    shot.write_bytes(b"\x89PNG")

    result = json.loads(feature_mcp.feature_mark_passing(
        1,
        test_summary="Logged in and saw dashboard",
        test_log="ok",
        screenshots=[str(shot), "/etc/passwd", "../outside.png"],
    ))
    assert result["success"] and result["evidence_recorded"]

    [entry] = _evidence(project)
    assert entry["result"] == "pass"
    assert entry["agent_type"] == "testing"
    assert entry["summary"] == "Logged in and saw dashboard"
    # Absolute path inside the project is made relative; outside paths are dropped
    assert entry["screenshots"] == [".playwright-cli/login.png"]


def test_mark_passing_without_evidence_keeps_behavior(project):
    result = json.loads(feature_mcp.feature_mark_passing(1))
    assert result["success"] and not result["evidence_recorded"]
    assert _evidence(project) is None
    assert "error" in json.loads(feature_mcp.feature_mark_passing(1))


def test_failing_and_record_evidence_append_and_cap(project):
    feature_mcp.feature_mark_failing(1, test_summary="Button does nothing")
    for i in range(feature_mcp.MAX_EVIDENCE_ENTRIES + 2):
        assert json.loads(feature_mcp.feature_record_evidence(1, "pass", f"run {i}"))["success"]

    entries = _evidence(project)
    assert len(entries) == feature_mcp.MAX_EVIDENCE_ENTRIES
    assert entries[-1]["summary"] == f"run {feature_mcp.MAX_EVIDENCE_ENTRIES + 1}"


def test_record_evidence_validation(project):
    assert "error" in json.loads(feature_mcp.feature_record_evidence(1, "pass", "   "))
    assert "error" in json.loads(feature_mcp.feature_record_evidence(999, "pass", "x"))


def test_long_log_is_truncated(project):
    feature_mcp.feature_record_evidence(1, "pass", "s", test_log="x" * (feature_mcp.MAX_EVIDENCE_LOG_CHARS + 50))
    [entry] = _evidence(project)
    assert entry["log"].endswith("[truncated 50 chars]")


def test_api_exposes_evidence(project, client):
    feature_mcp.feature_mark_passing(1, test_summary="Verified login")

    listing = client.get("/api/projects/demo/features").json()
    assert listing["done"][0]["evidence_count"] == 1

    body = client.get("/api/projects/demo/features/1/evidence").json()
    assert body["feature_id"] == 1
    assert body["evidence"][0]["summary"] == "Verified login"

    assert client.get("/api/projects/demo/features/42/evidence").status_code == 404


def test_screenshot_endpoint_only_serves_referenced_images(project, client):
    (project / ".playwright-cli").mkdir()
    (project / ".playwright-cli" / "ok.png").write_bytes(b"\x89PNG")
    (project / "secret.txt").write_text("secret")
    (project / "unreferenced.png").write_bytes(b"\x89PNG")
    feature_mcp.feature_record_evidence(
        1, "pass", "s", screenshots=[".playwright-cli/ok.png", "secret.txt", "missing.png"],
    )

    url = "/api/projects/demo/features/1/evidence/screenshot"
    ok = client.get(url, params={"path": ".playwright-cli/ok.png"})
    assert ok.status_code == 200 and ok.headers["content-type"] == "image/png"

    assert client.get(url, params={"path": "unreferenced.png"}).status_code == 404
    assert client.get(url, params={"path": "../etc/passwd"}).status_code == 404
    assert client.get(url, params={"path": "secret.txt"}).status_code == 400
    assert client.get(url, params={"path": "missing.png"}).status_code == 404
