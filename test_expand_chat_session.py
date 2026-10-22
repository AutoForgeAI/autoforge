"""
Expand Chat Session Tool Permission Tests
=========================================

Verifies that the "Expand Project" chat session grants and advertises the web
tools (WebFetch/WebSearch) so users can share reference URLs (issue #86),
while keeping file mutation and Bash disabled.

Run with: python -m pytest test_expand_chat_session.py -v
"""

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

from server.services import expand_chat_session
from server.services.expand_chat_session import ExpandChatSession


class _CapturingClient:
    """Stand-in for ClaudeSDKClient that records options and refuses to connect."""

    captured: dict[str, Any] = {}

    def __init__(self, options: Any) -> None:
        _CapturingClient.captured["options"] = options

    async def __aenter__(self) -> "_CapturingClient":
        settings_path = Path(_CapturingClient.captured["options"].settings)
        _CapturingClient.captured["settings"] = json.loads(settings_path.read_text(encoding="utf-8"))
        raise RuntimeError("stop after capture")

    async def __aexit__(self, *args: Any) -> None:
        return None


def _start_session(tmp_path: Path) -> dict[str, Any]:
    prompts_dir = tmp_path / ".autoforge" / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "app_spec.txt").write_text("<project_specification/>", encoding="utf-8")

    session = ExpandChatSession("demo", tmp_path)
    _CapturingClient.captured = {}

    async def run() -> list[dict]:
        chunks = [chunk async for chunk in session.start()]
        await session.close()
        return chunks

    with patch.object(expand_chat_session, "ClaudeSDKClient", _CapturingClient), \
            patch.object(expand_chat_session.shutil, "which", return_value="/usr/bin/claude"):
        chunks = asyncio.run(run())

    # The fake client aborts init, so the session must report an error
    assert any(c.get("type") == "error" for c in chunks)
    return _CapturingClient.captured


def test_web_tools_are_allowed(tmp_path: Path) -> None:
    options = _start_session(tmp_path)["options"]
    assert "WebFetch" in options.allowed_tools
    assert "WebSearch" in options.allowed_tools
    assert "WebFetch" not in options.disallowed_tools
    assert "WebSearch" not in options.disallowed_tools


def test_settings_file_allows_web_tools(tmp_path: Path) -> None:
    permissions = _start_session(tmp_path)["settings"]["permissions"]
    assert "WebFetch" in permissions["allow"]
    assert "WebSearch" in permissions["allow"]
    assert "WebFetch" not in permissions["deny"]
    assert "WebSearch" not in permissions["deny"]


def test_system_prompt_advertises_web_tools(tmp_path: Path) -> None:
    prompt = _start_session(tmp_path)["options"].system_prompt
    assert "WebFetch" in prompt
    assert "WebSearch" in prompt
    assert str(tmp_path.resolve()) in prompt  # $ARGUMENTS still substituted


def test_mutation_tools_remain_disabled(tmp_path: Path) -> None:
    captured = _start_session(tmp_path)
    options = captured["options"]
    for tool in ("Write", "Edit", "MultiEdit", "NotebookEdit", "Bash"):
        assert tool not in options.allowed_tools
        assert tool in options.disallowed_tools
        assert tool in captured["settings"]["permissions"]["deny"]
