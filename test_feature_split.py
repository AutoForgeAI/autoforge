"""
Tests for the feature_split MCP tool and the prompt rules that stop agents
from skipping or passing features they did not fully verify (issue #68).

Run with: python -m pytest test_feature_split.py
"""

import json

import pytest

import mcp_server.feature_mcp as feature_mcp
from api.database import Feature, create_database
from client import CODING_AGENT_TOOLS
from prompts import get_batch_feature_prompt, get_coding_prompt, get_single_feature_prompt


def _sub(name, depends_on_indices=None):
    item = {"category": "UI", "name": name, "description": f"{name} description", "steps": [f"Verify {name}"]}
    if depends_on_indices is not None:
        item["depends_on_indices"] = depends_on_indices
    return item


@pytest.fixture
def db(tmp_path, monkeypatch):
    engine, session_maker = create_database(tmp_path)
    monkeypatch.setattr(feature_mcp, "_session_maker", session_maker)
    session = session_maker()
    session.add_all([
        Feature(id=1, priority=1, category="Core", name="Base", description="d", steps=["s"], passes=True),
        Feature(id=2, priority=2, category="Core", name="Big", description="d", steps=["s"],
                in_progress=True, dependencies=[1]),
        Feature(id=3, priority=3, category="Core", name="Other", description="d", steps=["s"]),
    ])
    session.commit()
    session.close()
    yield session_maker
    engine.dispose()


def _get(session_maker, feature_id):
    session = session_maker()
    try:
        return session.query(Feature).filter(Feature.id == feature_id).first().to_dict()
    finally:
        session.close()


def test_split_creates_sub_features_and_blocks_parent(db):
    result = json.loads(feature_mcp.feature_split(
        feature_id=2,
        sub_features=[_sub("Part A"), _sub("Part B", [0])],
        reason="Too large for one session",
    ))
    assert result["success"] is True
    a_id, b_id = result["sub_feature_ids"]

    parent = _get(db, 2)
    assert parent["in_progress"] is False
    assert parent["passes"] is False
    assert parent["dependencies"] == sorted([1, a_id, b_id])

    part_a = _get(db, a_id)
    part_b = _get(db, b_id)
    assert part_a["priority"] == parent["priority"]
    assert part_a["dependencies"] == [1]
    assert part_b["dependencies"] == sorted([1, a_id])
    assert not part_a["passes"] and not part_b["passes"]


def test_split_rejects_passing_feature(db):
    result = json.loads(feature_mcp.feature_split(
        feature_id=1, sub_features=[_sub("A"), _sub("B")], reason="r",
    ))
    assert "error" in result


def test_split_rejects_missing_feature(db):
    result = json.loads(feature_mcp.feature_split(
        feature_id=999, sub_features=[_sub("A"), _sub("B")], reason="r",
    ))
    assert "error" in result


@pytest.mark.parametrize("subs", [
    [_sub("Only one")],
    [_sub(f"S{i}") for i in range(11)],
    [_sub("A"), {"category": "UI", "name": "B", "description": "d", "steps": []}],
    [_sub("A"), {"name": "B", "description": "d", "steps": ["s"]}],
    [_sub("A", [1]), _sub("B")],
    [_sub("A"), _sub("B", [1])],
    [_sub("A"), _sub("B", [0, 0])],
])
def test_split_rejects_invalid_input_without_changes(db, subs):
    result = json.loads(feature_mcp.feature_split(feature_id=2, sub_features=subs, reason="r"))
    assert "error" in result
    session = db()
    try:
        assert session.query(Feature).count() == 3
    finally:
        session.close()
    assert _get(db, 2)["dependencies"] == [1]
    assert _get(db, 2)["in_progress"] is True


def test_split_tool_available_to_coding_agent():
    assert "mcp__features__feature_split" in CODING_AGENT_TOOLS


def test_coding_prompt_forbids_unverified_passes():
    prompt = get_coding_prompt()
    assert "feature_split" in prompt
    assert "If the browser cannot be opened" in prompt
    assert "NEVER mark a feature passing if you implemented only part of it" in prompt


def test_yolo_prompt_keeps_split_but_drops_browser_rule():
    prompt = get_coding_prompt(yolo_mode=True)
    assert "feature_split" in prompt
    assert "If the browser cannot be opened" not in prompt


def test_assignment_headers_mention_split():
    assert "feature_split" in get_single_feature_prompt(5).split("---")[0]
    assert "feature_split" in get_batch_feature_prompt([5, 6]).split("---")[0]
