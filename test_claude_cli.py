"""
Unit tests for Claude CLI discovery.

Tests find_claude_cli() from env_constants.py, including explicit overrides
via CLAUDE_CLI_PATH / CLAUDE_PATH with paths containing spaces.
"""

import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import env_constants
from env_constants import find_claude_cli


def _make_executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


class TestFindClaudeCli(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        # Isolate from the real environment: empty PATH, fake home, no overrides
        env = {k: v for k, v in os.environ.items() if k not in env_constants.CLAUDE_CLI_ENV_VARS}
        env["PATH"] = str(self.tmp / "empty-path")
        self._env = mock.patch.dict(os.environ, env, clear=True)
        self._env.start()
        self._home = mock.patch.object(Path, "home", return_value=self.tmp / "home")
        self._home.start()

    def tearDown(self):
        self._home.stop()
        self._env.stop()
        self._tmp.cleanup()

    def test_returns_none_when_not_found(self):
        assert find_claude_cli() is None

    def test_env_override_with_spaces(self):
        cli = _make_executable(self.tmp / "OXFAM MONS" / "npm" / "claude.cmd")
        os.environ["CLAUDE_CLI_PATH"] = str(cli)
        assert find_claude_cli() == str(cli)

    def test_legacy_claude_path_alias(self):
        cli = _make_executable(self.tmp / "John Doe" / "claude")
        os.environ["CLAUDE_PATH"] = str(cli)
        assert find_claude_cli() == str(cli)

    def test_env_override_strips_quotes(self):
        cli = _make_executable(self.tmp / "with space" / "claude")
        os.environ["CLAUDE_CLI_PATH"] = f'  "{cli}"  '
        assert find_claude_cli() == str(cli)

    def test_invalid_override_falls_back_to_path(self):
        bin_dir = self.tmp / "bin dir"
        cli = _make_executable(bin_dir / "claude")
        os.environ["PATH"] = str(bin_dir)
        os.environ["CLAUDE_CLI_PATH"] = str(self.tmp / "missing" / "claude")
        assert find_claude_cli() == str(cli)

    def test_falls_back_to_common_install_location(self):
        if os.name == "nt":
            self.skipTest("POSIX fallback locations only")
        cli = _make_executable(self.tmp / "home" / ".npm-global" / "bin" / "claude")
        assert find_claude_cli() == str(cli)


if __name__ == "__main__":
    unittest.main()
