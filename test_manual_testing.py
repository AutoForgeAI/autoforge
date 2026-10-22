#!/usr/bin/env python3
"""
Manual Testing Lane Tests
=========================

Tests for the "needs manual testing" feature state: features the agent finished
coding but could not verify (e.g. native iOS apps) wait in a Manual Testing lane
until a human marks them passed or failed.

Run with: python -m pytest test_manual_testing.py
"""

import json
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.database import Feature, create_database
from api.dependency_resolver import (
    are_dependencies_satisfied,
    build_graph_data,
    get_blocked_features,
    get_ready_features,
    get_satisfied_ids,
)

# ---------------------------------------------------------------------------
# Dependency resolution
# ---------------------------------------------------------------------------

FEATURES = [
    {"id": 1, "priority": 1, "category": "a", "name": "one", "dependencies": [], "passes": True},
    {"id": 2, "priority": 2, "category": "a", "name": "two", "dependencies": [1], "passes": False,
     "needs_manual_testing": True},
    {"id": 3, "priority": 3, "category": "a", "name": "three", "dependencies": [2], "passes": False},
    {"id": 4, "priority": 4, "category": "a", "name": "four", "dependencies": [], "passes": False},
]


def test_satisfied_ids_include_manual_testing():
    assert get_satisfied_ids(FEATURES) == {1, 2}


def test_dependents_of_manual_testing_feature_are_unblocked():
    assert are_dependencies_satisfied(FEATURES[2], FEATURES)
    assert get_blocked_features(FEATURES) == []


def test_manual_testing_feature_is_not_ready_for_agents():
    ready_ids = [f["id"] for f in get_ready_features(FEATURES)]
    assert 2 not in ready_ids
    assert set(ready_ids) == {3, 4}


def test_graph_status_is_needs_manual_testing():
    statuses = {n["id"]: n["status"] for n in build_graph_data(FEATURES)["nodes"]}
    assert statuses[2] == "needs_manual_testing"
    assert statuses[3] == "pending"


# ---------------------------------------------------------------------------
# Database migration
# ---------------------------------------------------------------------------

def test_migration_adds_columns_to_legacy_db(tmp_path):
    db_dir = tmp_path / ".autoforge"
    db_dir.mkdir()
    conn = sqlite3.connect(db_dir / "features.db")
    conn.execute("""
        CREATE TABLE features (
            id INTEGER PRIMARY KEY, priority INTEGER, category VARCHAR(100), name VARCHAR(255),
            description TEXT, steps JSON, passes BOOLEAN, in_progress BOOLEAN, dependencies JSON
        )
    """)
    conn.execute("INSERT INTO features VALUES (1, 1, 'c', 'n', 'd', '[]', 0, 0, NULL)")
    conn.commit()
    conn.close()

    engine, SessionLocal = create_database(tmp_path)
    try:
        session = SessionLocal()
        f = session.query(Feature).first()
        assert f.to_dict()["needs_manual_testing"] is False
        assert f.to_dict()["manual_testing_notes"] is None
        session.close()
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------

@pytest.fixture
def project(tmp_path, monkeypatch):
    """A project with features in each relevant state, served by the features router."""
    from server.routers import features as features_router

    engine, SessionLocal = create_database(tmp_path)
    session = SessionLocal()
    session.add_all([
        Feature(id=1, priority=1, category="c", name="Login screen", description="d", steps=[],
                passes=False, in_progress=False, needs_manual_testing=True,
                manual_testing_notes="Open the app in the iOS simulator and log in"),
        Feature(id=2, priority=2, category="c", name="Profile", description="d", steps=[],
                passes=False, in_progress=False, dependencies=[1]),
        Feature(id=3, priority=3, category="c", name="Busy", description="d", steps=[],
                passes=False, in_progress=True),
    ])
    session.commit()
    session.close()

    monkeypatch.setattr(features_router, "_get_project_path", lambda name: tmp_path)
    app = FastAPI()
    app.include_router(features_router.router)
    yield TestClient(app), SessionLocal
    engine.dispose()


def test_list_features_has_manual_testing_lane(project):
    client, _ = project
    data = client.get("/api/projects/demo/features").json()
    assert [f["id"] for f in data["needs_manual_testing"]] == [1]
    assert data["needs_manual_testing"][0]["manual_testing_notes"].startswith("Open the app")
    # Feature 1 is no longer hidden in pending, and its dependent is not blocked
    pending = {f["id"]: f for f in data["pending"]}
    assert 1 not in pending
    assert pending[2]["blocked"] is False


def test_manual_test_pass(project):
    client, SessionLocal = project
    resp = client.post("/api/projects/demo/features/1/manual-test", json={"result": "pass"})
    assert resp.status_code == 200
    assert resp.json()["passes"] is True
    assert resp.json()["needs_manual_testing"] is False

    session = SessionLocal()
    f = session.get(Feature, 1)
    assert f.passes and not f.needs_manual_testing
    session.close()


def test_manual_test_fail_returns_to_pending_with_feedback(project):
    client, _ = project
    resp = client.post(
        "/api/projects/demo/features/1/manual-test",
        json={"result": "fail", "feedback": "Keyboard covers the password field"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["passes"] is False
    assert body["needs_manual_testing"] is False
    assert "Keyboard covers the password field" in body["manual_testing_notes"]

    data = client.get("/api/projects/demo/features").json()
    assert 1 in [f["id"] for f in data["pending"]]


def test_manual_pass_allowed_for_idle_pending_feature(project):
    client, _ = project
    resp = client.post("/api/projects/demo/features/2/manual-test", json={"result": "pass"})
    assert resp.status_code == 200
    assert resp.json()["passes"] is True


def test_manual_test_rejections(project):
    client, _ = project
    # Can't fail a feature that isn't awaiting manual testing
    assert client.post("/api/projects/demo/features/2/manual-test", json={"result": "fail"}).status_code == 400
    # Can't pass a feature an agent is working on
    assert client.post("/api/projects/demo/features/3/manual-test", json={"result": "pass"}).status_code == 409
    # Invalid verdict
    assert client.post("/api/projects/demo/features/1/manual-test", json={"result": "maybe"}).status_code == 422
    # Missing feature
    assert client.post("/api/projects/demo/features/99/manual-test", json={"result": "pass"}).status_code == 404


# ---------------------------------------------------------------------------
# MCP tool
# ---------------------------------------------------------------------------

@pytest.fixture
def mcp_module(tmp_path, monkeypatch):
    feature_mcp = pytest.importorskip("mcp_server.feature_mcp")

    engine, SessionLocal = create_database(tmp_path)
    session = SessionLocal()
    session.add_all([
        Feature(id=1, priority=1, category="c", name="Push notifications", description="d", steps=[],
                passes=False, in_progress=True),
        Feature(id=2, priority=2, category="c", name="Settings", description="d", steps=[],
                passes=False, in_progress=False, dependencies=[1]),
    ])
    session.commit()
    session.close()

    monkeypatch.setattr(feature_mcp, "_session_maker", SessionLocal)
    yield feature_mcp
    engine.dispose()


def test_mcp_mark_needs_manual_testing(mcp_module):
    result = json.loads(mcp_module.feature_mark_needs_manual_testing(1, "Test on a real device"))
    assert result["success"] is True

    feature = json.loads(mcp_module.feature_get_by_id(1))
    assert feature["needs_manual_testing"] is True
    assert feature["in_progress"] is False
    assert feature["manual_testing_notes"] == "Test on a real device"

    # Agents can't re-claim it, but its dependent is now ready
    assert "error" in json.loads(mcp_module.feature_mark_in_progress(1))
    assert "error" in json.loads(mcp_module.feature_claim_and_get(1))
    ready_ids = [f["id"] for f in json.loads(mcp_module.feature_get_ready())["features"]]
    assert ready_ids == [2]

    stats = json.loads(mcp_module.feature_get_stats())
    assert stats["needs_manual_testing"] == 1

    # Marking passing clears the manual-testing flag
    assert json.loads(mcp_module.feature_mark_passing(1))["success"] is True
    feature = json.loads(mcp_module.feature_get_by_id(1))
    assert feature["passes"] is True
    assert feature["needs_manual_testing"] is False


def test_mcp_mark_needs_manual_testing_rejects_passing_feature(mcp_module):
    mcp_module.feature_mark_passing(1)
    result = json.loads(mcp_module.feature_mark_needs_manual_testing(1, "notes"))
    assert "already passing" in result["error"]
