"""
Tests for Claude CLI discovery and folder-browser path handling (issue #16).

Run with: python -m pytest test_claude_cli.py
"""

import asyncio
import os
import stat
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

import claude_cli
from claude_cli import find_claude_cli
from server.routers.filesystem import list_directory


def _make_executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


@pytest.fixture
def clean_env(monkeypatch):
    for var in claude_cli.CLAUDE_PATH_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    return monkeypatch


def test_claude_path_with_spaces(tmp_path, clean_env):
    cli = _make_executable(tmp_path / "OXFAM MONS" / "npm" / "claude")
    clean_env.setenv("CLAUDE_PATH", str(cli))
    assert find_claude_cli() == str(cli)


@pytest.mark.parametrize("quote", ['"', "'"])
def test_claude_path_with_surrounding_quotes(tmp_path, clean_env, quote):
    cli = _make_executable(tmp_path / "User Name" / "claude")
    clean_env.setenv("CLAUDE_PATH", f"  {quote}{cli}{quote} ")
    assert find_claude_cli() == str(cli)


def test_claude_cli_path_alias(tmp_path, clean_env):
    cli = _make_executable(tmp_path / "bin" / "claude")
    clean_env.setenv("CLAUDE_CLI_PATH", str(cli))
    assert find_claude_cli() == str(cli)


def test_invalid_claude_path_falls_back_to_path_lookup(tmp_path, clean_env):
    cli = _make_executable(tmp_path / "on path" / "claude")
    clean_env.setenv("CLAUDE_PATH", str(tmp_path / "missing" / "claude"))
    clean_env.setenv("PATH", str(cli.parent))
    assert find_claude_cli() == str(cli)


def test_falls_back_to_known_install_locations(tmp_path, clean_env):
    cli = _make_executable(tmp_path / "fallback" / "claude")
    clean_env.setenv("PATH", str(tmp_path / "empty"))
    clean_env.setattr(claude_cli, "_candidate_install_paths", lambda: [tmp_path / "nope", cli])
    assert find_claude_cli() == str(cli)


def test_returns_none_when_not_found(tmp_path, clean_env):
    clean_env.setenv("PATH", str(tmp_path / "empty"))
    clean_env.setattr(claude_cli, "_candidate_install_paths", lambda: [])
    assert find_claude_cli() is None


# ---------------------------------------------------------------------------
# Folder browser: hidden directories and pasted paths
# ---------------------------------------------------------------------------

def _list(path: str | None, show_hidden: bool = False):
    return asyncio.run(list_directory(path=path, show_hidden=show_hidden))


@pytest.fixture
def browse_root():
    # Linux blocks /tmp in the browser, so build the fixture under the home directory
    base = Path.home() / f".autoforge-test-browse-{os.getpid()}"
    (base / "visible").mkdir(parents=True, exist_ok=True)
    (base / ".github").mkdir(exist_ok=True)
    (base / ".claude").mkdir(exist_ok=True)
    yield base
    for child in base.iterdir():
        child.rmdir()
    base.rmdir()


def test_hidden_directories_excluded_by_default(browse_root):
    names = {e.name for e in _list(str(browse_root)).entries}
    assert names == {"visible"}


def test_hidden_directories_listed_when_requested(browse_root):
    entries = {e.name: e for e in _list(str(browse_root), show_hidden=True).entries}
    assert set(entries) == {"visible", ".github", ".claude"}
    assert entries[".github"].is_hidden is True
    assert entries["visible"].is_hidden is False


def test_tilde_path_is_expanded(browse_root):
    result = _list(f"~/{browse_root.name}")
    assert result.current_path == browse_root.resolve().as_posix()


def test_relative_path_rejected():
    with pytest.raises(HTTPException) as exc:
        _list("some/relative/dir")
    assert exc.value.status_code == 400


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX path semantics")
def test_sensitive_hidden_directories_stay_blocked(browse_root):
    # .ssh etc. remain blocked even when hidden folders are shown
    result = _list(str(Path.home()), show_hidden=True)
    assert ".ssh" not in {e.name for e in result.entries}
