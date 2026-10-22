"""
Tests for the feature_report_bug MCP tool and its exposure to the assistant.

Run with: python -m pytest test_feature_report_bug.py
"""

import json

import pytest

import mcp_server.feature_mcp as feature_mcp
from api.database import Feature, create_database
from server.services.assistant_chat_session import (
    ASSISTANT_FEATURE_TOOLS,
    DISALLOWED_ASSISTANT_TOOLS,
)


@pytest.fixture
def session_maker(tmp_path, monkeypatch):
    _engine, maker = create_database(tmp_path)
    monkeypatch.setattr(feature_mcp, "_session_maker", maker)
    yield maker
    _engine.dispose()


def _add_feature(maker, **overrides) -> int:
    session = maker()
    try:
        feature = Feature(
            priority=1,
            category="Auth",
            name="User login",
            description="Users can log in.",
            steps=["Open login page", "Submit valid credentials"],
            passes=True,
            in_progress=False,
        )
        for key, value in overrides.items():
            setattr(feature, key, value)
        session.add(feature)
        session.commit()
        return int(feature.id)
    finally:
        session.close()


def _get(maker, feature_id: int) -> Feature:
    session = maker()
    try:
        feature: Feature = session.query(Feature).filter(Feature.id == feature_id).one()
        session.expunge(feature)
        return feature
    finally:
        session.close()


def test_reopens_passing_feature_with_bug_details(session_maker):
    fid = _add_feature(session_maker)

    result = json.loads(feature_mcp.feature_report_bug(
        feature_id=fid,
        bug_description="Empty password is accepted",
        steps=["Submit with an empty password", "  ", "Verify a validation error is shown"],
    ))

    assert result["success"] is True
    assert result["was_passing"] is True
    feature = _get(session_maker, fid)
    assert feature.passes is False
    assert feature.in_progress is False
    assert feature.description.startswith("Users can log in.")
    assert "**Bug report:** Empty password is accepted" in feature.description
    assert feature.steps == [
        "Open login page",
        "Submit valid credentials",
        "Submit with an empty password",
        "Verify a validation error is shown",
    ]
    # Priority is unchanged; no new feature is created
    assert feature.priority == 1
    session = session_maker()
    try:
        assert session.query(Feature).count() == 1
    finally:
        session.close()


def test_pending_feature_without_steps(session_maker):
    fid = _add_feature(session_maker, passes=False)

    result = json.loads(feature_mcp.feature_report_bug(feature_id=fid, bug_description="Typo in label"))

    assert result["success"] is True
    assert result["was_passing"] is False
    feature = _get(session_maker, fid)
    assert feature.steps == ["Open login page", "Submit valid credentials"]
    assert "Typo in label" in feature.description


def test_rejects_in_progress_feature(session_maker):
    fid = _add_feature(session_maker, passes=False, in_progress=True)

    result = json.loads(feature_mcp.feature_report_bug(feature_id=fid, bug_description="Broken"))

    assert "error" in result
    feature = _get(session_maker, fid)
    assert feature.in_progress is True
    assert feature.description == "Users can log in."


def test_missing_feature_and_blank_description(session_maker):
    assert "error" in json.loads(feature_mcp.feature_report_bug(feature_id=999, bug_description="x"))

    fid = _add_feature(session_maker)
    assert "error" in json.loads(feature_mcp.feature_report_bug(feature_id=fid, bug_description="   "))
    assert _get(session_maker, fid).passes is True


def test_assistant_can_report_bugs_but_not_mark_status():
    assert "mcp__features__feature_report_bug" in ASSISTANT_FEATURE_TOOLS
    assert "mcp__features__feature_get_graph" in ASSISTANT_FEATURE_TOOLS
    assert "mcp__features__feature_report_bug" not in DISALLOWED_ASSISTANT_TOOLS
    assert "mcp__features__feature_mark_passing" in DISALLOWED_ASSISTANT_TOOLS
    assert "mcp__features__feature_mark_failing" in DISALLOWED_ASSISTANT_TOOLS
