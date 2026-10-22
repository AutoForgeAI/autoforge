"""
Tests that web-UI chat sessions (spec creation, project expansion) have no
shell access and tell the model so (issue #14).

The web UI has no way for the user to approve a tool call, so a Bash call
can only fail with "This command requires approval". The model must not
have the tool, and must know it cannot ask the user for approval.
"""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from autoforge_paths import get_prompts_dir
from server.services import expand_chat_session, spec_chat_session
from server.services.chat_constants import NO_SHELL_PROMPT_NOTE


class _CapturingClient:
    """Stand-in for ClaudeSDKClient that records options and aborts startup."""

    captured: list = []

    def __init__(self, options):
        _CapturingClient.captured.append(options)

    async def __aenter__(self):
        raise RuntimeError("stop after capturing options")


async def _drain(gen):
    return [chunk async for chunk in gen]


def _run_session(module, session_cls, project_dir: Path):
    _CapturingClient.captured = []
    with (
        patch.object(module, "ClaudeSDKClient", _CapturingClient),
        patch.object(module.shutil, "which", return_value="/usr/bin/claude"),
        patch("registry.get_effective_sdk_env", return_value={}),
        patch("registry.get_effort_setting", return_value=None),
    ):
        session = session_cls("demo", project_dir)
        chunks = asyncio.run(_drain(session.start()))
    assert chunks and chunks[-1]["type"] == "error"
    assert len(_CapturingClient.captured) == 1
    return _CapturingClient.captured[0]


class TestSpecChatSessionNoShell(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_dir = Path(self._tmp.name) / "proj"

    def tearDown(self):
        self._tmp.cleanup()

    def test_bash_removed_and_denied(self):
        options = _run_session(spec_chat_session, spec_chat_session.SpecChatSession, self.project_dir)

        assert "Bash" in options.disallowed_tools
        assert "Bash" not in options.allowed_tools
        settings = json.loads(Path(options.settings).read_text())
        assert "Bash" in settings["permissions"]["deny"]

    def test_prompt_explains_no_shell(self):
        _run_session(spec_chat_session, spec_chat_session.SpecChatSession, self.project_dir)

        # Spec session delivers its system prompt through the project CLAUDE.md
        claude_md = (self.project_dir / "CLAUDE.md").read_text(encoding="utf-8")
        assert claude_md.endswith(NO_SHELL_PROMPT_NOTE)


class TestExpandChatSessionNoShell(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_dir = Path(self._tmp.name) / "proj"
        prompts_dir = get_prompts_dir(self.project_dir)
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "app_spec.txt").write_text("<project_specification/>", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_bash_removed_and_prompt_explains_no_shell(self):
        options = _run_session(expand_chat_session, expand_chat_session.ExpandChatSession, self.project_dir)

        assert "Bash" in options.disallowed_tools
        assert options.system_prompt.endswith(NO_SHELL_PROMPT_NOTE)


class TestNoShellPromptNote(unittest.TestCase):
    def test_note_tells_model_not_to_ask_for_approval(self):
        note = NO_SHELL_PROMPT_NOTE.lower()
        assert "no bash" in note
        assert "never ask the user to approve" in note


if __name__ == "__main__":
    unittest.main()
