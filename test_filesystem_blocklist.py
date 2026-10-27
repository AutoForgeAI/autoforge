"""
Tests for the filesystem browser blocklist (server/routers/filesystem.py).

Regression coverage for issue #159: when the server runs as root (WSL,
containers) the home directory is /root, which is also a blocked system
path. The user's own home must stay browsable while sensitive
subdirectories inside it remain blocked.
"""

import asyncio
import sys
from pathlib import Path

import pytest

from server.routers import filesystem


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Point Path.home() at a temp dir and register it as a blocked system path."""
    home = tmp_path / "root"
    home.mkdir()
    (home / ".ssh").mkdir()
    (home / "projects").mkdir()

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(filesystem, "LINUX_BLOCKED", {str(home), str(tmp_path / "etc")})
    monkeypatch.setattr(filesystem, "MACOS_BLOCKED", {str(home), str(tmp_path / "etc")})
    monkeypatch.setattr(filesystem, "WINDOWS_BLOCKED", {str(home), str(tmp_path / "etc")})
    filesystem.get_blocked_paths.cache_clear()
    filesystem.get_home_dir.cache_clear()
    yield home
    filesystem.get_blocked_paths.cache_clear()
    filesystem.get_home_dir.cache_clear()


def test_home_is_not_blocked_even_if_listed_as_system_path(fake_home):
    assert not filesystem.is_path_blocked(fake_home)


def test_subdirectory_of_home_is_allowed(fake_home):
    assert not filesystem.is_path_blocked(fake_home / "projects")
    assert not filesystem.is_path_blocked(fake_home / "projects" / "new-app")


def test_sensitive_directory_in_home_still_blocked(fake_home):
    assert filesystem.is_path_blocked(fake_home / ".ssh")
    assert filesystem.is_path_blocked(fake_home / ".ssh" / "keys")


def test_other_system_paths_still_blocked(fake_home):
    assert filesystem.is_path_blocked(fake_home.parent / "etc")
    assert filesystem.is_path_blocked(fake_home.parent / "etc" / "passwd")


def test_home_nested_under_blocked_path_is_allowed(tmp_path, monkeypatch):
    """A home like /var/lib/svc under blocked /var must remain browsable."""
    var = tmp_path / "var"
    home = var / "lib" / "svc"
    home.mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    attr = {"win32": "WINDOWS_BLOCKED", "darwin": "MACOS_BLOCKED"}.get(sys.platform, "LINUX_BLOCKED")
    monkeypatch.setattr(filesystem, attr, {str(var)})
    filesystem.get_blocked_paths.cache_clear()
    filesystem.get_home_dir.cache_clear()
    try:
        assert not filesystem.is_path_blocked(home)
        assert filesystem.is_path_blocked(var)
        assert filesystem.is_path_blocked(var / "log")
    finally:
        filesystem.get_blocked_paths.cache_clear()
        filesystem.get_home_dir.cache_clear()


def test_list_directory_defaults_to_home(fake_home):
    result = asyncio.run(filesystem.list_directory(path=None, show_hidden=False))
    assert result.current_path == fake_home.as_posix()
    names = [e.name for e in result.entries]
    assert "projects" in names
