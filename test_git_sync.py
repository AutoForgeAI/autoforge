"""
Tests for git_sync.py (opt-in auto-push to a Git remote).

Uses real git repositories in temporary directories with a local bare repo
acting as the remote, so no network access is required.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

import git_sync
from git_sync import maybe_push_to_remote, push_to_remote


def _run(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    _run(project, "init", "-b", "main")
    _run(project, "config", "user.email", "test@example.com")
    _run(project, "config", "user.name", "Test")
    _run(project, "config", "commit.gpgsign", "false")
    return project


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(bare)], check=True, capture_output=True)
    return bare


def _commit(repo: Path, name: str = "file.txt") -> None:
    (repo / name).write_text(name)
    _run(repo, "add", name)
    _run(repo, "commit", "-m", f"add {name}")


def test_not_a_git_repo(tmp_path: Path):
    ok, msg = push_to_remote(tmp_path)
    assert not ok
    assert "not a git repository" in msg


def test_no_commits(repo: Path):
    ok, msg = push_to_remote(repo)
    assert not ok
    assert "no commits" in msg


def test_no_remote(repo: Path):
    _commit(repo)
    ok, msg = push_to_remote(repo)
    assert not ok
    assert "no git remote" in msg


def test_detached_head(repo: Path, remote: Path):
    _commit(repo)
    _run(repo, "remote", "add", "origin", str(remote))
    _run(repo, "checkout", "--detach")
    ok, msg = push_to_remote(repo)
    assert not ok
    assert "detached" in msg


def test_pushes_and_sets_upstream(repo: Path, remote: Path):
    _commit(repo)
    _run(repo, "remote", "add", "origin", str(remote))
    _run(repo, "checkout", "-b", "feature/x")

    ok, msg = push_to_remote(repo)
    assert ok, msg
    assert "origin/feature/x" in msg
    assert _run(repo, "rev-parse", "--abbrev-ref", "@{u}") == "origin/feature/x"
    assert _run(remote, "rev-parse", "feature/x") == _run(repo, "rev-parse", "HEAD")

    # Subsequent commits use the existing upstream
    _commit(repo, "second.txt")
    ok, msg = push_to_remote(repo)
    assert ok, msg
    assert _run(remote, "rev-parse", "feature/x") == _run(repo, "rev-parse", "HEAD")


def test_rejected_push_is_reported_not_raised(repo: Path, remote: Path, tmp_path: Path):
    _commit(repo)
    _run(repo, "remote", "add", "origin", str(remote))
    assert push_to_remote(repo)[0]

    # Someone else pushes a diverging commit to the remote
    other = tmp_path / "other"
    subprocess.run(["git", "clone", str(remote), str(other)], check=True, capture_output=True)
    _run(other, "config", "user.email", "o@example.com")
    _run(other, "config", "user.name", "Other")
    _run(other, "config", "commit.gpgsign", "false")
    _commit(other, "other.txt")
    _run(other, "push")

    _commit(repo, "local.txt")
    ok, msg = push_to_remote(repo)
    assert not ok
    assert "failed" in msg


def test_maybe_push_respects_setting(repo: Path, remote: Path):
    _commit(repo)
    _run(repo, "remote", "add", "origin", str(remote))

    with patch.object(git_sync, "is_auto_push_enabled", return_value=False):
        maybe_push_to_remote(repo)
    assert subprocess.run(
        ["git", "rev-parse", "--verify", "main"], cwd=remote, capture_output=True
    ).returncode != 0

    with patch.object(git_sync, "is_auto_push_enabled", return_value=True):
        maybe_push_to_remote(repo)
    assert _run(remote, "rev-parse", "main") == _run(repo, "rev-parse", "HEAD")
