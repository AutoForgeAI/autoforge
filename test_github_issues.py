#!/usr/bin/env python3
"""
GitHub Issue Import Tests
=========================

Tests for converting GitHub issues into features and the import endpoints.
GitHub API calls are mocked; no network access is needed.

Run with: python -m pytest test_github_issues.py
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.routers import github as github_router
from server.services import github_issues as gh


def _issue(number=7, title="Add dark mode", body="", labels=None, comments=0):
    return {
        "number": number,
        "title": title,
        "body": body,
        "state": "open",
        "url": f"https://github.com/acme/app/issues/{number}",
        "labels": labels or [],
        "author": "alice",
        "comments": comments,
        "created_at": None,
        "updated_at": None,
    }


# --- pure helpers -----------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/acme/app.git",
        "https://github.com/acme/app",
        "https://token@github.com/acme/app.git",
        "git@github.com:acme/app.git",
        "ssh://git@github.com/acme/app.git",
    ],
)
def test_parse_github_remote(url):
    assert gh.parse_github_remote(url) == "acme/app"


@pytest.mark.parametrize("url", ["https://gitlab.com/acme/app.git", "/local/path", "git@bitbucket.org:a/b.git"])
def test_parse_non_github_remote(url):
    assert gh.parse_github_remote(url) is None


@pytest.mark.parametrize("repo", ["acme", "acme/app/extra", "../etc", "acme/..", "a b/c", "acme/app?x=1"])
def test_validate_repo_rejects_bad_input(repo):
    with pytest.raises(gh.GitHubError):
        gh.validate_repo(repo)


def test_validate_repo_accepts_and_strips_git():
    assert gh.validate_repo(" acme/my.app-2.git ") == "acme/my.app-2"


def test_issue_to_feature_uses_task_list_as_steps():
    body = "Users want dark mode.\n<!-- template junk -->\n- [ ] Add toggle\n- [x] Persist choice\n* [ ] Respect OS"
    f = gh.issue_to_feature("acme/app", _issue(body=body, labels=["enhancement", "ui"]))
    assert f["name"] == "#7 Add dark mode"
    assert f["category"] == "enhancement"
    assert f["steps"] == ["Add toggle", "Persist choice", "Respect OS"]
    assert "template junk" not in f["description"]
    assert gh.source_marker("https://github.com/acme/app/issues/7") in f["description"].splitlines()


def test_issue_to_feature_defaults_and_comments():
    f = gh.issue_to_feature("acme/app", _issue(body=""), [{"author": "bob", "body": "Please also do X"}])
    assert f["category"] == gh.DEFAULT_CATEGORY
    assert len(f["steps"]) == 2
    assert "Add dark mode" in f["description"]
    assert "@bob: Please also do X" in f["description"]


def test_issue_to_feature_truncates_long_content():
    f = gh.issue_to_feature("acme/app", _issue(title="x" * 400, body="y" * 50000))
    assert len(f["name"]) <= gh.MAX_NAME_CHARS
    assert len(f["description"]) <= gh.MAX_DESCRIPTION_CHARS
    assert f["description"].endswith(gh.source_marker("https://github.com/acme/app/issues/7"))


def test_get_auth_prefers_env(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "abc")
    assert gh.get_auth().token == "abc"


# --- endpoints --------------------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(github_router, "_get_project_path", lambda name: tmp_path)
    monkeypatch.setattr(gh, "get_auth", lambda: gh.GitHubAuth(None, "none"))
    monkeypatch.setattr(gh, "detect_repo", lambda d: "acme/app")

    issues = {7: _issue(7, body="- [ ] Add toggle"), 8: _issue(8, title="Fix login", comments=1)}
    monkeypatch.setattr(gh, "list_issues", lambda repo, auth, state="open": list(issues.values()))
    monkeypatch.setattr(gh, "get_issue", lambda repo, n, auth: issues[n])
    monkeypatch.setattr(gh, "get_issue_comments", lambda repo, n, auth: [{"author": "bob", "body": "+1"}])

    app = FastAPI()
    app.include_router(github_router.router)
    return TestClient(app)


def test_import_creates_features_and_skips_duplicates(client):
    resp = client.post("/api/projects/demo/github/import", json={"repo": "acme/app", "issue_numbers": [7, 8, 7]})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["created"] == 2
    assert data["skipped"] == []
    names = [f["name"] for f in data["features"]]
    assert names == ["#7 Add dark mode", "#8 Fix login"]
    assert data["features"][0]["steps"] == ["Add toggle"]
    assert "@bob: +1" in data["features"][1]["description"]
    assert all(not f["passes"] for f in data["features"])

    listing = client.get("/api/projects/demo/github/issues").json()
    assert listing["repo"] == "acme/app"
    imported = {i["number"]: i["imported_feature_id"] for i in listing["issues"]}
    assert imported[7] == data["features"][0]["id"]
    assert imported[8] == data["features"][1]["id"]

    again = client.post("/api/projects/demo/github/import", json={"repo": "acme/app", "issue_numbers": [7]}).json()
    assert again["created"] == 0
    assert again["skipped"] == [7]


def test_import_rejects_invalid_repo(client):
    resp = client.post("/api/projects/demo/github/import", json={"repo": "../x", "issue_numbers": [1]})
    assert resp.status_code == 400


def test_list_without_remote_asks_for_repo(client, monkeypatch):
    monkeypatch.setattr(gh, "detect_repo", lambda d: None)
    resp = client.get("/api/projects/demo/github/issues")
    assert resp.status_code == 400
    assert "owner/name" in resp.json()["detail"]


def test_github_errors_are_surfaced(client, monkeypatch):
    def boom(*a, **k):
        raise gh.GitHubError("GitHub API rate limit exceeded.", 429)

    monkeypatch.setattr(gh, "list_issues", boom)
    resp = client.get("/api/projects/demo/github/issues?repo=acme/app")
    assert resp.status_code == 429
    assert "rate limit" in resp.json()["detail"]
