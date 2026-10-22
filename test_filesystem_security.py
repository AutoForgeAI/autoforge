#!/usr/bin/env python3
"""
Filesystem Browser Security Tests
=================================

Tests for the blocked-path checks used by the folder browser and project creation.
Run with: python -m pytest test_filesystem_security.py -v
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from server.routers import filesystem
from server.routers.filesystem import is_path_blocked

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="Linux blocklist tests")


def _clear_caches() -> None:
    filesystem.get_system_blocked_paths.cache_clear()
    filesystem.get_sensitive_blocked_paths.cache_clear()
    filesystem.get_browsable_home.cache_clear()


@pytest.fixture
def fake_home(monkeypatch):
    """Point Path.home() at a given directory and reset the cached blocklists."""

    def _set(home: str) -> Path:
        home_path = Path(home)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: home_path))
        _clear_caches()
        return home_path

    yield _set
    _clear_caches()


def test_root_home_is_browsable(fake_home):
    """Running as root (common in WSL) must allow browsing /root (issue #159)."""
    fake_home("/root")
    assert not is_path_blocked(Path("/root"))
    assert not is_path_blocked(Path("/root/projects/my-app"))


def test_root_home_still_blocks_credentials(fake_home):
    fake_home("/root")
    assert is_path_blocked(Path("/root/.ssh"))
    assert is_path_blocked(Path("/root/.aws/credentials"))


def test_home_under_var_does_not_unblock_var(fake_home):
    """Homes under /var (e.g. Fedora Silverblue) are browsable, the rest of /var is not."""
    fake_home("/var/home/alice")
    assert not is_path_blocked(Path("/var/home/alice/code"))
    assert is_path_blocked(Path("/var"))
    assert is_path_blocked(Path("/var/log"))


def test_system_paths_blocked_for_regular_user(fake_home):
    fake_home("/home/alice")
    assert is_path_blocked(Path("/root"))
    assert is_path_blocked(Path("/etc"))
    assert is_path_blocked(Path("/usr/bin"))
    assert not is_path_blocked(Path("/home/alice/code"))
    assert not is_path_blocked(Path("/mnt/d/dev_projects"))


def test_filesystem_root_home_is_ignored(fake_home):
    """HOME=/ must not exempt every system directory from the blocklist."""
    fake_home("/")
    assert is_path_blocked(Path("/etc"))
    assert is_path_blocked(Path("/root"))
