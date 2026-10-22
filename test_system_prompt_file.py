"""
Regression tests for issue #8: long chat system prompts must not be passed
on the Claude CLI command line (Windows limit ~8191 chars, "The command line
is too long").

Each chat session writes its system prompt to a file under ``.autoforge/`` and
hands it to the CLI via ``--system-prompt-file``.  These tests stub the SDK
client, capture the options each session builds, and render the real CLI
command from them.
"""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport

from server.services import expand_chat_session, spec_chat_session

WINDOWS_CMDLINE_LIMIT = 8191


class _FakeClient:
    """Stand-in for ClaudeSDKClient that records options and fails on connect."""

    captured: list = []

    def __init__(self, options):
        self.options = options
        _FakeClient.captured.append(options)

    async def __aenter__(self):
        raise RuntimeError("stop after options are built")

    async def __aexit__(self, *args):
        return None


def _render_command(options) -> list[str]:
    transport = SubprocessCLITransport(prompt="", options=options)
    transport._cli_path = "claude"
    return transport._build_command()


async def _drain(gen):
    return [chunk async for chunk in gen]


class TestSystemPromptFile(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_dir = Path(self._tmp.name) / "my-app"
        self.project_dir.mkdir()
        _FakeClient.captured = []

    def tearDown(self):
        self._tmp.cleanup()

    def _assert_prompt_passed_by_file(self, options, skill_file: str):
        cmd = _render_command(options)
        self.assertIn("--system-prompt-file", cmd)
        self.assertNotIn("--system-prompt", cmd)
        cmdline_len = sum(len(arg) + 1 for arg in cmd)
        self.assertLess(cmdline_len, WINDOWS_CMDLINE_LIMIT)

        prompt_path = Path(cmd[cmd.index("--system-prompt-file") + 1])
        self.assertTrue(prompt_path.is_file())
        self.assertEqual(prompt_path.parent, (self.project_dir / ".autoforge").resolve())
        # The file holds the full skill with $ARGUMENTS replaced by the project path
        skill = (spec_chat_session.ROOT_DIR / ".claude" / "commands" / skill_file).read_text(encoding="utf-8")
        expected = skill.replace("$ARGUMENTS", str(self.project_dir.resolve()))
        self.assertEqual(prompt_path.read_text(encoding="utf-8"), expected)
        return prompt_path

    def test_spec_session_uses_prompt_file(self):
        session = spec_chat_session.SpecChatSession("my-app", self.project_dir)
        with patch.object(spec_chat_session, "ClaudeSDKClient", _FakeClient), \
                patch.object(spec_chat_session.shutil, "which", return_value="claude"):
            chunks = asyncio.run(_drain(session.start()))
        self.assertEqual(chunks[-1]["type"], "error")
        self.assertEqual(len(_FakeClient.captured), 1)

        prompt_path = self._assert_prompt_passed_by_file(_FakeClient.captured[0], "create-spec.md")
        # The project's CLAUDE.md must no longer be overwritten with the skill
        self.assertFalse((self.project_dir / "CLAUDE.md").exists())

        asyncio.run(session.close())
        self.assertFalse(prompt_path.exists())

    def test_expand_session_uses_prompt_file(self):
        prompts_dir = self.project_dir / ".autoforge" / "prompts"
        prompts_dir.mkdir(parents=True)
        (prompts_dir / "app_spec.txt").write_text("<project_specification/>", encoding="utf-8")

        session = expand_chat_session.ExpandChatSession("my-app", self.project_dir)
        with patch.object(expand_chat_session, "ClaudeSDKClient", _FakeClient), \
                patch.object(expand_chat_session.shutil, "which", return_value="claude"):
            chunks = asyncio.run(_drain(session.start()))
        self.assertEqual(chunks[-1]["type"], "error")
        self.assertEqual(len(_FakeClient.captured), 1)

        prompt_path = self._assert_prompt_passed_by_file(_FakeClient.captured[0], "expand-project.md")

        asyncio.run(session.close())
        self.assertFalse(prompt_path.exists())


if __name__ == "__main__":
    unittest.main()
