#!/usr/bin/env python3
"""
Test Evidence Tests
===================

Tests for recording test evidence on features (issue #69): evidence building,
screenshot path validation, the feature MCP tools, and the screenshot endpoint.
Run with: python -m pytest test_test_evidence.py -v
"""

import json
import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from api.database import Feature, create_database, dispose_engine
from api.test_evidence import build_test_evidence, resolve_screenshot_path

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


@pytest.fixture
def project_dir(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    yield project
    dispose_engine(project)


@pytest.fixture
def screenshot(project_dir):
    shots = project_dir / ".playwright-cli"
    shots.mkdir()
    path = shots / "page.png"
    path.write_bytes(PNG_BYTES)
    return path


@pytest.fixture
def session_maker(project_dir):
    _, session_maker = create_database(project_dir)
    session = session_maker()
    session.add_all([
        Feature(id=1, priority=1, category="core", name="Login", description="d", steps=["s"]),
        Feature(id=2, priority=2, category="core", name="Logout", description="d", steps=["s"], passes=True),
    ])
    session.commit()
    session.close()
    return session_maker


@pytest.fixture
def mcp_module(project_dir, session_maker, monkeypatch):
    from mcp_server import feature_mcp
    monkeypatch.setattr(feature_mcp, "PROJECT_DIR", project_dir.resolve())
    monkeypatch.setattr(feature_mcp, "_session_maker", session_maker)
    return feature_mcp


def _evidence(session_maker, feature_id):
    session = session_maker()
    try:
        return session.query(Feature).filter(Feature.id == feature_id).first().test_evidence
    finally:
        session.close()


# =============================================================================
# resolve_screenshot_path
# =============================================================================


class TestResolveScreenshotPath:
    def test_relative_image_inside_project(self, project_dir, screenshot):
        assert resolve_screenshot_path(project_dir, ".playwright-cli/page.png") == screenshot.resolve()

    def test_absolute_image_inside_project(self, project_dir, screenshot):
        assert resolve_screenshot_path(project_dir, str(screenshot)) == screenshot.resolve()

    def test_rejects_traversal(self, project_dir):
        assert resolve_screenshot_path(project_dir, "../outside.png") is None

    def test_rejects_absolute_outside(self, project_dir, tmp_path):
        assert resolve_screenshot_path(project_dir, str(tmp_path / "outside.png")) is None

    def test_rejects_non_image(self, project_dir):
        assert resolve_screenshot_path(project_dir, ".autoforge/features.db") is None

    def test_rejects_empty_and_null_byte(self, project_dir):
        assert resolve_screenshot_path(project_dir, "") is None
        assert resolve_screenshot_path(project_dir, "a\x00.png") is None


# =============================================================================
# build_test_evidence
# =============================================================================


class TestBuildTestEvidence:
    def test_nothing_supplied_returns_none(self, project_dir):
        evidence, warnings = build_test_evidence(project_dir, 1, "passing")
        assert evidence is None
        assert warnings == []

    def test_builds_and_copies_screenshot(self, project_dir, screenshot):
        evidence, warnings = build_test_evidence(
            project_dir, 7, "passing",
            summary="  works  ",
            test_log=["step 1 -> ok", "", "  step 2 -> ok "],
            screenshots=[".playwright-cli/page.png", ".playwright-cli/page.png"],
        )
        assert warnings == []
        assert evidence["result"] == "passing"
        assert evidence["summary"] == "works"
        assert evidence["test_log"] == ["step 1 -> ok", "step 2 -> ok"]
        assert evidence["recorded_at"]
        # Duplicate collapsed, copied into the evidence folder
        assert len(evidence["screenshots"]) == 1
        stored = evidence["screenshots"][0]
        assert stored.startswith(".autoforge/evidence/feature_7/")
        assert (project_dir / stored).read_bytes() == PNG_BYTES

    def test_rejects_bad_screenshots_with_warnings(self, project_dir, tmp_path):
        outside = tmp_path / "secret.png"
        outside.write_bytes(PNG_BYTES)
        evidence, warnings = build_test_evidence(
            project_dir, 1, "failing",
            summary="broken",
            screenshots=[str(outside), "missing.png", "notes.txt"],
        )
        assert evidence["screenshots"] == []
        assert len(warnings) == 3

    def test_limits_applied(self, project_dir):
        evidence, _ = build_test_evidence(
            project_dir, 1, "passing", summary="x" * 10000, test_log=["s"] * 200,
        )
        assert len(evidence["summary"]) == 4000
        assert len(evidence["test_log"]) == 50

    def test_screenshot_already_in_evidence_dir_not_recopied(self, project_dir):
        evidence_dir = project_dir / ".autoforge" / "evidence" / "feature_3"
        evidence_dir.mkdir(parents=True)
        (evidence_dir / "shot.png").write_bytes(PNG_BYTES)
        evidence, _ = build_test_evidence(
            project_dir, 3, "passing", screenshots=[".autoforge/evidence/feature_3/shot.png"],
        )
        assert evidence["screenshots"] == [".autoforge/evidence/feature_3/shot.png"]
        assert len(list(evidence_dir.iterdir())) == 1


# =============================================================================
# Feature MCP tools
# =============================================================================


class TestMcpTools:
    def test_mark_passing_records_evidence(self, mcp_module, session_maker, screenshot):
        result = json.loads(mcp_module.feature_mark_passing(
            1, summary="verified", test_log=["a -> ok"], screenshots=[".playwright-cli/page.png"],
        ))
        assert result["success"] is True
        assert result["evidence_recorded"] is True
        evidence = _evidence(session_maker, 1)
        assert evidence["result"] == "passing"
        assert evidence["summary"] == "verified"
        assert len(evidence["screenshots"]) == 1

    def test_mark_passing_without_evidence_still_works(self, mcp_module, session_maker):
        result = json.loads(mcp_module.feature_mark_passing(1))
        assert result["success"] is True
        assert result["evidence_recorded"] is False
        assert _evidence(session_maker, 1) is None

    def test_mark_passing_reports_screenshot_warnings(self, mcp_module):
        result = json.loads(mcp_module.feature_mark_passing(1, summary="ok", screenshots=["../x.png"]))
        assert result["success"] is True
        assert len(result["warnings"]) == 1

    def test_mark_passing_already_passing_keeps_evidence_untouched(self, mcp_module, session_maker):
        result = json.loads(mcp_module.feature_mark_passing(2, summary="should not be stored"))
        assert "error" in result
        assert _evidence(session_maker, 2) is None

    def test_mark_failing_records_evidence(self, mcp_module, session_maker):
        result = json.loads(mcp_module.feature_mark_failing(2, summary="button does nothing"))
        assert result["evidence_recorded"] is True
        assert "test_evidence" not in result["feature"]  # kept out of agent context
        evidence = _evidence(session_maker, 2)
        assert evidence["result"] == "failing"
        assert evidence["summary"] == "button does nothing"

    def test_mark_failing_without_evidence_preserves_previous(self, mcp_module, session_maker):
        mcp_module.feature_mark_passing(1, summary="first")
        mcp_module.feature_mark_failing(1)
        assert _evidence(session_maker, 1)["summary"] == "first"

    def test_record_evidence(self, mcp_module, session_maker):
        result = json.loads(mcp_module.feature_record_evidence(2, test_log=["re-tested -> ok"]))
        assert result["success"] is True
        evidence = _evidence(session_maker, 2)
        assert evidence["result"] == "passing"
        assert evidence["test_log"] == ["re-tested -> ok"]

    def test_record_evidence_requires_content(self, mcp_module):
        assert "error" in json.loads(mcp_module.feature_record_evidence(2))

    def test_record_evidence_unknown_feature(self, mcp_module):
        assert "error" in json.loads(mcp_module.feature_record_evidence(999, summary="x"))

    def test_get_by_id_excludes_evidence(self, mcp_module):
        mcp_module.feature_mark_passing(1, summary="verified")
        assert "test_evidence" not in json.loads(mcp_module.feature_get_by_id(1))


# =============================================================================
# REST API
# =============================================================================


@pytest.fixture
def client(project_dir, session_maker, monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from server.routers import features as features_router

    monkeypatch.setattr(features_router, "_get_project_path", lambda name: project_dir)
    app = FastAPI()
    app.include_router(features_router.router)
    return TestClient(app)


def _set_evidence(session_maker, feature_id, evidence):
    session = session_maker()
    feature = session.query(Feature).filter(Feature.id == feature_id).first()
    feature.test_evidence = evidence
    session.commit()
    session.close()


class TestApi:
    def test_feature_response_includes_evidence(self, client, session_maker):
        _set_evidence(session_maker, 2, {"result": "passing", "summary": "ok", "test_log": [],
                                         "screenshots": [], "recorded_at": "2026-01-01T00:00:00+00:00"})
        body = client.get("/api/projects/proj/features/2").json()
        assert body["test_evidence"]["summary"] == "ok"
        assert client.get("/api/projects/proj/features/1").json()["test_evidence"] is None

    def test_serves_screenshot(self, client, session_maker, screenshot):
        _set_evidence(session_maker, 2, {"screenshots": [".playwright-cli/page.png"]})
        resp = client.get("/api/projects/proj/features/2/evidence/screenshots/0")
        assert resp.status_code == 200
        assert resp.content == PNG_BYTES
        assert resp.headers["content-type"] == "image/png"

    def test_index_out_of_range(self, client, session_maker, screenshot):
        _set_evidence(session_maker, 2, {"screenshots": [".playwright-cli/page.png"]})
        assert client.get("/api/projects/proj/features/2/evidence/screenshots/1").status_code == 404
        assert client.get("/api/projects/proj/features/1/evidence/screenshots/0").status_code == 404

    def test_tampered_path_is_not_served(self, client, session_maker, project_dir, tmp_path):
        outside = tmp_path / "secret.png"
        outside.write_bytes(PNG_BYTES)
        (project_dir / "notes.txt").write_text("hi")
        _set_evidence(session_maker, 2, {"screenshots": [str(outside), "../secret.png", "notes.txt"]})
        for i in range(3):
            assert client.get(f"/api/projects/proj/features/2/evidence/screenshots/{i}").status_code == 404
