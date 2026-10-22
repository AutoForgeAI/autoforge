#!/usr/bin/env python3
"""
Chat Session Command Length Tests
=================================

Regression tests for issue #44: on Windows the Claude CLI is a ``claude.cmd``
shim run through cmd.exe, which rejects command lines longer than 8191
characters ("The command line is too long."). The assistant, spec and expand
chat sessions must keep large content (system prompts, MCP config) in files
instead of passing it as CLI arguments.

Run with: python -m pytest test_chat_command_length.py
"""

import asyncio
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport

from server.services import assistant_chat_session, expand_chat_session, spec_chat_session

# cmd.exe maximum command line length
WINDOWS_CMD_LIMIT = 8191


class _StopStart(Exception):
    """Raised by the fake client to stop start() once options are captured."""


class _CapturingClient:
    captured: list = []

    def __init__(self, options):
        _CapturingClient.captured.append(options)
        raise _StopStart()


async def _drain(gen):
    return [chunk async for chunk in gen]


class TestChatCommandLength(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        # Deeply nested project path to mimic a realistic worst case on Windows
        self.project_dir = Path(self.tmp, *(["very_long_directory_name_segment"] * 6), "MyProject")
        prompts_dir = self.project_dir / ".autoforge" / "prompts"
        prompts_dir.mkdir(parents=True)
        # Large app spec: the assistant embeds up to 5000 chars of it in its prompt
        (prompts_dir / "app_spec.txt").write_text("<project_specification>" + "x" * 20000, encoding="utf-8")
        _CapturingClient.captured = []

        fake_cli = str(Path(self.tmp, "npm", "claude.cmd"))
        self.patches = [
            patch("registry.get_effective_sdk_env", return_value={}),
            patch("registry.get_effort_setting", return_value="high"),
            patch("shutil.which", return_value=fake_cli),
        ]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _command_line(self, session_module, session):
        with patch.object(session_module, "ClaudeSDKClient", _CapturingClient):
            chunks = asyncio.run(_drain(session.start()))
        self.assertEqual(len(_CapturingClient.captured), 1, f"client not created: {chunks}")
        options = _CapturingClient.captured[0]
        cmd = SubprocessCLITransport(prompt="", options=options)._build_command()
        return options, subprocess.list2cmdline(cmd)

    def _assert_mcp_config_is_file(self, options):
        self.assertIsInstance(options.mcp_servers, str)
        config = json.loads(Path(options.mcp_servers).read_text(encoding="utf-8"))
        self.assertIn("features", config["mcpServers"])

    def test_assistant_command_fits_windows_limit(self):
        session = assistant_chat_session.AssistantChatSession("MyProject", self.project_dir)
        options, cmdline = self._command_line(assistant_chat_session, session)
        self.assertLess(len(cmdline), WINDOWS_CMD_LIMIT)
        self._assert_mcp_config_is_file(options)

    def test_expand_command_fits_windows_limit(self):
        session = expand_chat_session.ExpandChatSession("MyProject", self.project_dir)
        options, cmdline = self._command_line(expand_chat_session, session)
        self.assertLess(len(cmdline), WINDOWS_CMD_LIMIT)
        self._assert_mcp_config_is_file(options)
        self.assertEqual(options.system_prompt["type"], "file")
        prompt = Path(options.system_prompt["path"]).read_text(encoding="utf-8")
        self.assertIn(str(self.project_dir.resolve()), prompt)

        # Temp files are removed when the session closes
        temp_files = [Path(options.settings), Path(options.mcp_servers), Path(options.system_prompt["path"])]
        asyncio.run(session.close())
        for temp_file in temp_files:
            self.assertFalse(temp_file.exists(), f"{temp_file} not cleaned up")

    def test_spec_command_fits_windows_limit(self):
        session = spec_chat_session.SpecChatSession("MyProject", self.project_dir)
        _, cmdline = self._command_line(spec_chat_session, session)
        self.assertLess(len(cmdline), WINDOWS_CMD_LIMIT)


if __name__ == "__main__":
    unittest.main()
