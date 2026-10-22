"""
Expand Chat Session Tests
=========================

Verifies that features created through the feature MCP tools during an
expand-project chat are reported to the UI as ``features_created`` events.

Run with: python -m pytest test_expand_chat_session.py
"""

import asyncio
import json
from pathlib import Path

from claude_agent_sdk.types import (
    AssistantMessage,
    ResultMessage,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from server.services.expand_chat_session import ExpandChatSession, parse_created_features

BULK = "mcp__features__feature_create_bulk"
SINGLE = "mcp__features__feature_create"

BULK_INPUT = {
    "features": [
        {"category": "style", "name": "Dark theme toggle", "description": "d", "steps": ["s"]},
        {"category": "functional", "name": "Theme persists", "description": "d", "steps": ["s"]},
    ]
}


def _text_content(payload: dict) -> list[dict]:
    return [{"type": "text", "text": json.dumps(payload)}]


def test_parse_bulk_with_ids():
    result = _text_content({"created": 2, "with_dependencies": 0, "feature_ids": [7, 8]})
    assert parse_created_features(BULK, BULK_INPUT, result) == [
        {"id": 7, "name": "Dark theme toggle", "category": "style"},
        {"id": 8, "name": "Theme persists", "category": "functional"},
    ]


def test_parse_bulk_without_ids_string_content():
    result = json.dumps({"created": 2, "with_dependencies": 0})
    features = parse_created_features(BULK, BULK_INPUT, result)
    assert [f["id"] for f in features] == [None, None]
    assert [f["name"] for f in features] == ["Dark theme toggle", "Theme persists"]


def test_parse_single():
    result = _text_content({
        "success": True,
        "feature": {"id": 3, "name": "Export CSV", "category": "data"},
    })
    assert parse_created_features(SINGLE, {}, result) == [
        {"id": 3, "name": "Export CSV", "category": "data"},
    ]


def test_parse_errors_and_garbage():
    assert parse_created_features(BULK, BULK_INPUT, _text_content({"error": "missing fields"})) == []
    assert parse_created_features(BULK, BULK_INPUT, "not json") == []
    assert parse_created_features(BULK, BULK_INPUT, None) == []
    assert parse_created_features(BULK, BULK_INPUT, _text_content({"created": 0})) == []


class _FakeClient:
    def __init__(self, messages):
        self._messages = messages

    async def query(self, _message):
        pass

    async def receive_response(self):
        for msg in self._messages:
            yield msg


def _run_query(messages) -> tuple[ExpandChatSession, list[dict]]:
    session = ExpandChatSession("demo", Path("."))
    session.client = _FakeClient(messages)  # type: ignore[assignment]

    async def collect():
        return [chunk async for chunk in session._query_claude("go")]

    return session, asyncio.run(collect())


def _result_message():
    return ResultMessage(
        subtype="success", duration_ms=1, duration_api_ms=1, is_error=False,
        num_turns=1, session_id="s",
    )


def test_query_emits_features_created():
    session, chunks = _run_query([
        AssistantMessage(content=[
            TextBlock(text="Great! I'll create these 2 features now."),
            ToolUseBlock(id="tu1", name=BULK, input=BULK_INPUT),
        ], model="m"),
        UserMessage(content=[ToolResultBlock(
            tool_use_id="tu1",
            content=_text_content({"created": 2, "with_dependencies": 0, "feature_ids": [7, 8]}),
        )]),
        _result_message(),
    ])

    created = [c for c in chunks if c["type"] == "features_created"]
    assert len(created) == 1
    assert created[0]["count"] == 2
    assert session.get_features_created() == 2
    assert session.created_feature_ids == [7, 8]


def test_query_ignores_failed_and_unrelated_tools():
    session, chunks = _run_query([
        AssistantMessage(content=[
            ToolUseBlock(id="tu1", name=BULK, input=BULK_INPUT),
            ToolUseBlock(id="tu2", name="Read", input={"file_path": "x"}),
        ], model="m"),
        UserMessage(content=[
            ToolResultBlock(tool_use_id="tu1", content="MCP server not connected", is_error=True),
            ToolResultBlock(tool_use_id="tu2", content=json.dumps({"created": 5})),
        ]),
        _result_message(),
    ])

    assert not [c for c in chunks if c["type"] == "features_created"]
    assert session.get_features_created() == 0
