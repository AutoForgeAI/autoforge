#!/usr/bin/env python3
"""
Feature Import Tests
====================

Tests for the feature_import_file MCP tool (importing features from a JSON
file inside the project directory).
Run with: python -m pytest test_feature_import.py
"""

import json

import pytest

import mcp_server.feature_mcp as feature_mcp
from api.database import Feature, create_database

SAMPLE_FEATURES = [
    {
        "category": "style",
        "name": "Dark theme",
        "description": "App supports a dark theme",
        "steps": ["Open settings", "Toggle dark theme", "Verify colors change"],
    },
    {
        "category": "style",
        "name": "Theme persistence",
        "description": "Selected theme survives a reload",
        "steps": ["Select dark theme", "Reload page", "Verify dark theme is active"],
        "depends_on_indices": [0],
    },
]


@pytest.fixture
def project(tmp_path, monkeypatch):
    """Point the MCP server at a fresh project with an initialized database."""
    project_dir = tmp_path.resolve()
    engine, session_maker = create_database(project_dir)
    monkeypatch.setattr(feature_mcp, "PROJECT_DIR", project_dir)
    monkeypatch.setattr(feature_mcp, "_session_maker", session_maker)
    yield project_dir, session_maker
    engine.dispose()


def _features(session_maker):
    session = session_maker()
    try:
        return session.query(Feature).order_by(Feature.priority).all()
    finally:
        session.close()


def _import(path):
    return json.loads(feature_mcp.feature_import_file(path))


def test_imports_array_with_dependencies(project):
    project_dir, session_maker = project
    (project_dir / "prompts").mkdir()
    (project_dir / "prompts" / "theme_features.json").write_text(json.dumps(SAMPLE_FEATURES), encoding="utf-8")

    result = _import("prompts/theme_features.json")

    assert result == {"created": 2, "with_dependencies": 1, "file": "prompts/theme_features.json"}
    features = _features(session_maker)
    assert [f.name for f in features] == ["Dark theme", "Theme persistence"]
    assert features[1].dependencies == [features[0].id]
    assert not any(f.passes for f in features)


def test_imports_object_with_features_key(project):
    project_dir, session_maker = project
    (project_dir / "features.json").write_text(json.dumps({"features": SAMPLE_FEATURES[:1]}), encoding="utf-8")

    result = _import(str(project_dir / "features.json"))

    assert result["created"] == 1
    assert len(_features(session_maker)) == 1


def test_rejects_path_outside_project(project, tmp_path_factory):
    _, session_maker = project
    outside = tmp_path_factory.mktemp("outside") / "features.json"
    outside.write_text(json.dumps(SAMPLE_FEATURES), encoding="utf-8")

    assert "inside the project" in _import(str(outside))["error"]
    assert "inside the project" in _import("../" + outside.parent.name + "/features.json")["error"]
    assert _features(session_maker) == []


@pytest.mark.parametrize(
    "content, message",
    [
        ("{not json", "not valid JSON"),
        ("[]", "non-empty JSON array"),
        ('{"other": []}', "non-empty JSON array"),
        ('["just a string"]', "not a JSON object"),
        ('[{"name": "missing fields"}]', "missing required fields"),
    ],
)
def test_rejects_invalid_content(project, content, message):
    project_dir, session_maker = project
    (project_dir / "bad.json").write_text(content, encoding="utf-8")

    assert message in _import("bad.json")["error"]
    assert _features(session_maker) == []


def test_missing_file(project):
    assert "File not found" in _import("nope.json")["error"]
