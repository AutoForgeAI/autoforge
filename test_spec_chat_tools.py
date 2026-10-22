"""
Spec Chat Tool Restriction Tests
================================

The web UI cannot answer permission prompts, so the spec creation agent must
not be offered tools that would need approval (issue #14), and it must be told
about that limitation up front.

Run with: python -m pytest test_spec_chat_tools.py
"""

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

from server.services import spec_chat_session
from server.services.spec_chat_session import (
    SPEC_DISALLOWED_TOOLS,
    SpecChatSession,
)


class _FakeClient:
    """Stand-in for ClaudeSDKClient that records its options."""

    last_options = None

    def __init__(self, options):
        _FakeClient.last_options = options

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None


async def _run_start(session: SpecChatSession) -> list[dict]:
    async def fake_query(self, message):
        yield {"type": "text", "content": "hi"}

    with patch.object(spec_chat_session, "ClaudeSDKClient", _FakeClient), \
            patch.object(SpecChatSession, "_query_claude", fake_query):
        return [chunk async for chunk in session.start()]


def _start_session(tmp_path: Path) -> list[dict]:
    session = SpecChatSession("demo", tmp_path / "demo")
    return asyncio.run(_run_start(session))


def test_bash_is_removed_from_spec_agent(tmp_path):
    chunks = _start_session(tmp_path)
    assert not any(c["type"] == "error" for c in chunks), chunks

    options = _FakeClient.last_options
    assert "Bash" in options.disallowed_tools
    assert "Bash" not in options.allowed_tools
    for tool in SPEC_DISALLOWED_TOOLS:
        assert tool not in options.allowed_tools


def test_settings_file_denies_bash(tmp_path):
    _start_session(tmp_path)

    settings = json.loads(Path(_FakeClient.last_options.settings).read_text())
    assert "Bash" in settings["permissions"]["deny"]


def test_prompt_tells_agent_it_cannot_run_commands(tmp_path):
    _start_session(tmp_path)

    claude_md = (tmp_path / "demo" / "CLAUDE.md").read_text(encoding="utf-8")
    assert "CANNOT run shell commands" in claude_md
    assert "Never ask the user to approve" in claude_md
    assert "Parquet" in claude_md
