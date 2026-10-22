#!/usr/bin/env python3
"""
Feature Bug Report Tests
========================

Tests for the feature_report_bug MCP tool used by the project assistant.
Run with: python -m pytest test_feature_report_bug.py
"""

import json
import tempfile
from pathlib import Path

import pytest

import mcp_server.feature_mcp as feature_mcp
from api.database import Feature, create_database


@pytest.fixture
def db():
    with tempfile.TemporaryDirectory() as tmp:
        engine, session_maker = create_database(Path(tmp))
        feature_mcp._session_maker = session_maker
        session = session_maker()
        session.add_all([
            Feature(id=1, priority=1, category="UI", name="Login", description="Login form",
                    steps=["Open /login"], passes=True, in_progress=False),
            Feature(id=2, priority=2, category="UI", name="Logout", description="Logout button",
                    steps=["Click logout"], passes=False, in_progress=True),
            Feature(id=3, priority=3, category="API", name="Search", description="Search API",
                    steps=["GET /search"], passes=False, in_progress=False),
        ])
        session.commit()
        session.close()
        yield session_maker
        feature_mcp._session_maker = None
        engine.dispose()


def _get(session_maker, feature_id):
    session = session_maker()
    try:
        return session.query(Feature).filter(Feature.id == feature_id).first().to_dict()
    finally:
        session.close()


def test_report_bug_on_passing_feature_sends_it_back_to_pending(db):
    result = json.loads(feature_mcp.feature_report_bug(
        1, "Submitting valid credentials shows a blank page", ["Log in with valid credentials", "See dashboard"]
    ))

    assert result["success"] is True
    assert result["was_passing"] is True
    feature = _get(db, 1)
    assert feature["passes"] is False
    assert feature["in_progress"] is False
    assert "BUG REPORT: Submitting valid credentials shows a blank page" in feature["description"]
    assert feature["description"].startswith("Login form")
    assert feature["steps"] == ["Open /login", "Log in with valid credentials", "See dashboard"]
    # Moved ahead of every other feature
    assert feature["priority"] < min(_get(db, i)["priority"] for i in (2, 3))


def test_report_bug_without_steps_keeps_existing_steps(db):
    result = json.loads(feature_mcp.feature_report_bug(3, "Returns 500 on empty query"))

    assert result["success"] is True
    assert result["was_passing"] is False
    assert _get(db, 3)["steps"] == ["GET /search"]


def test_report_bug_refuses_in_progress_feature(db):
    result = json.loads(feature_mcp.feature_report_bug(2, "Button does nothing"))

    assert "error" in result
    feature = _get(db, 2)
    assert feature["description"] == "Logout button"
    assert feature["in_progress"] is True


def test_report_bug_unknown_feature(db):
    result = json.loads(feature_mcp.feature_report_bug(99, "Whatever"))

    assert "not found" in result["error"]


def test_assistant_can_use_report_bug_tool():
    from server.services.assistant_chat_session import (
        ASSISTANT_FEATURE_TOOLS,
        DISALLOWED_ASSISTANT_TOOLS,
    )

    assert "mcp__features__feature_report_bug" in ASSISTANT_FEATURE_TOOLS
    assert "mcp__features__feature_report_bug" not in DISALLOWED_ASSISTANT_TOOLS
