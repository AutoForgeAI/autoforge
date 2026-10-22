"""Tests for git_sync auto-push helper."""

import subprocess
from pathlib import Path

import pytest

import git_sync


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    _git(project, "init", "-q", "-b", "main")
    _git(project, "config", "user.email", "test@example.com")
    _git(project, "config", "user.name", "Test")
    (project / "README.md").write_text("hello\n")
    _git(project, "add", ".")
    _git(project, "commit", "-q", "-m", "initial")
    return project


@pytest.fixture
def remote(tmp_path: Path) -> Path:
    bare = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], check=True)
    return bare


def test_not_a_repo(tmp_path: Path):
    ok, msg = git_sync.push_current_branch(tmp_path)
    assert not ok
    assert "not a git repository" in msg


def test_no_remote_skips(repo: Path):
    ok, msg = git_sync.push_current_branch(repo)
    assert not ok
    assert "no 'origin' remote" in msg


def test_pushes_to_origin_and_sets_upstream(repo: Path, remote: Path):
    _git(repo, "remote", "add", "origin", str(remote))
    ok, msg = git_sync.push_current_branch(repo)
    assert ok, msg
    assert _git(remote, "rev-parse", "main") == _git(repo, "rev-parse", "HEAD")
    assert _git(repo, "rev-parse", "--abbrev-ref", "@{u}") == "origin/main"

    # Subsequent commits are pushed via the upstream
    (repo / "feature.txt").write_text("feature\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "feature")
    ok, msg = git_sync.push_current_branch(repo)
    assert ok, msg
    assert _git(remote, "rev-parse", "main") == _git(repo, "rev-parse", "HEAD")


def test_pushes_feature_branch(repo: Path, remote: Path):
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "checkout", "-q", "-b", "feature/login")
    ok, msg = git_sync.push_current_branch(repo)
    assert ok, msg
    assert "feature/login" in msg
    assert _git(remote, "rev-parse", "feature/login") == _git(repo, "rev-parse", "HEAD")


def test_detached_head_skips(repo: Path, remote: Path):
    _git(repo, "remote", "add", "origin", str(remote))
    _git(repo, "checkout", "-q", "--detach")
    ok, msg = git_sync.push_current_branch(repo)
    assert not ok
    assert "detached" in msg


def test_rejected_push_reports_failure(repo: Path, remote: Path, tmp_path: Path):
    _git(repo, "remote", "add", "origin", str(remote))
    assert git_sync.push_current_branch(repo)[0]

    # Someone else pushes a diverging commit; we must not force over it
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(remote), str(other)], check=True)
    _git(other, "config", "user.email", "o@example.com")
    _git(other, "config", "user.name", "Other")
    (other / "other.txt").write_text("x\n")
    _git(other, "add", ".")
    _git(other, "commit", "-q", "-m", "other")
    _git(other, "push", "-q")
    remote_head = _git(remote, "rev-parse", "main")

    (repo / "mine.txt").write_text("y\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "mine")
    ok, msg = git_sync.push_current_branch(repo)
    assert not ok
    assert "failed" in msg
    assert _git(remote, "rev-parse", "main") == remote_head


@pytest.mark.parametrize("value,expected", [("1", True), ("true", True), ("0", False), ("false", False)])
def test_env_var_overrides_setting(monkeypatch, value: str, expected: bool):
    monkeypatch.setenv(git_sync.GIT_AUTO_PUSH_ENV, value)
    assert git_sync.is_auto_push_enabled() is expected


def test_setting_used_when_env_unset(monkeypatch):
    import registry

    monkeypatch.delenv(git_sync.GIT_AUTO_PUSH_ENV, raising=False)
    monkeypatch.setattr(registry, "get_setting", lambda key, default=None: "true")
    assert git_sync.is_auto_push_enabled() is True
    monkeypatch.setattr(registry, "get_setting", lambda key, default=None: None)
    assert git_sync.is_auto_push_enabled() is False
