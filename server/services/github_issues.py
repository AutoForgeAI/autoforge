"""
GitHub Issues Service
=====================

Fetches issues from a GitHub repository and converts them into AutoForge
features, so an existing project's backlog can be handed to the coding agent.

Authentication (all optional; public repos work without a token, subject to
GitHub's unauthenticated rate limit of 60 requests/hour):
1. ``GITHUB_TOKEN`` or ``GH_TOKEN`` environment variable
2. ``gh auth token`` if the GitHub CLI is installed and logged in
"""

import json
import logging
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
REQUEST_TIMEOUT = 15

# owner/name as GitHub allows them; also keeps user input out of the URL path
REPO_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]{1,100}$")

# https://github.com/owner/repo(.git), git@github.com:owner/repo(.git), ssh://git@github.com/owner/repo
_REMOTE_RE = re.compile(
    r"^(?:https?://(?:[^@/]+@)?github\.com/|git@github\.com:|ssh://git@github\.com/)"
    r"(?P<repo>[^/\s]+/[^/\s]+?)(?:\.git)?/?$"
)

# GitHub task list items: "- [ ] do thing" / "* [x] done thing"
_TASK_RE = re.compile(r"^\s*[-*+]\s+\[[ xX]\]\s+(?P<text>.+?)\s*$", re.MULTILINE)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

MAX_BODY_CHARS = 4000
MAX_COMMENT_CHARS = 1000
MAX_COMMENTS = 10
MAX_DESCRIPTION_CHARS = 8000
MAX_NAME_CHARS = 255
MAX_CATEGORY_CHARS = 100
DEFAULT_CATEGORY = "GitHub Issue"


class GitHubError(Exception):
    """Error talking to GitHub, carrying an HTTP status suitable for the API response."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class GitHubAuth:
    token: str | None
    source: str  # "env", "gh", or "none"


def validate_repo(repo: str) -> str:
    """Validate and normalize an ``owner/name`` repository string."""
    repo = repo.strip()
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not REPO_RE.match(repo) or ".." in repo:
        raise GitHubError(f"Invalid repository '{repo}'. Use the form owner/name.", 400)
    return repo


def parse_github_remote(url: str) -> str | None:
    """Extract ``owner/name`` from a GitHub remote URL, or None if it isn't GitHub."""
    match = _REMOTE_RE.match(url.strip())
    if not match:
        return None
    try:
        return validate_repo(match.group("repo"))
    except GitHubError:
        return None


def detect_repo(project_dir: Path) -> str | None:
    """Detect the GitHub repository from the project's git remotes (origin first)."""
    git = shutil.which("git")
    if not git or not (project_dir / ".git").exists():
        return None
    try:
        result = subprocess.run(
            [git, "-C", str(project_dir), "remote", "-v"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None

    remotes: dict[str, str] = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] not in remotes:
            remotes[parts[0]] = parts[1]

    ordered = sorted(remotes.items(), key=lambda kv: (kv[0] != "origin", kv[0] != "upstream", kv[0]))
    for _, url in ordered:
        repo = parse_github_remote(url)
        if repo:
            return repo
    return None


def get_auth() -> GitHubAuth:
    """Find a GitHub token from the environment or the gh CLI."""
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        token = os.environ.get(var, "").strip()
        if token:
            return GitHubAuth(token, "env")

    gh = shutil.which("gh")
    if gh:
        try:
            result = subprocess.run([gh, "auth", "token"], capture_output=True, text=True, timeout=5)
            token = result.stdout.strip()
            if result.returncode == 0 and token:
                return GitHubAuth(token, "gh")
        except (OSError, subprocess.SubprocessError):
            pass
    return GitHubAuth(None, "none")


def _request(path: str, auth: GitHubAuth, params: dict[str, Any] | None = None) -> Any:
    url = f"{GITHUB_API}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "autoforge",
    }
    if auth.token:
        headers["Authorization"] = f"Bearer {auth.token}"

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:  # noqa: S310 - fixed https host
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            hint = "" if auth.token else " If it is private, set GITHUB_TOKEN or run `gh auth login`."
            raise GitHubError(f"Repository or issue not found on GitHub.{hint}", 404) from e
        if e.code in (401, 403):
            if e.headers.get("X-RateLimit-Remaining") == "0":
                msg = "GitHub API rate limit exceeded."
                if not auth.token:
                    msg += " Set GITHUB_TOKEN or run `gh auth login` for a higher limit."
                raise GitHubError(msg, 429) from e
            raise GitHubError("GitHub denied access. Check your GITHUB_TOKEN / gh login permissions.", 403) from e
        raise GitHubError(f"GitHub API error (HTTP {e.code}).", 502) from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise GitHubError(f"Could not reach GitHub: {e}", 502) from e


def _summarize_issue(issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "number": issue["number"],
        "title": issue.get("title") or "",
        "body": issue.get("body") or "",
        "state": issue.get("state") or "open",
        "url": issue.get("html_url") or "",
        "labels": [lbl.get("name", "") for lbl in issue.get("labels", []) if isinstance(lbl, dict)],
        "author": (issue.get("user") or {}).get("login", ""),
        "comments": issue.get("comments", 0),
        "created_at": issue.get("created_at"),
        "updated_at": issue.get("updated_at"),
    }


def list_issues(repo: str, auth: GitHubAuth, state: str = "open", limit: int = 100) -> list[dict[str, Any]]:
    """List issues (excluding pull requests), newest first."""
    repo = validate_repo(repo)
    issues: list[dict[str, Any]] = []
    page = 1
    while len(issues) < limit and page <= 5:
        data = _request(
            f"/repos/{repo}/issues",
            auth,
            {"state": state, "per_page": 100, "page": page, "sort": "created", "direction": "desc"},
        )
        if not isinstance(data, list) or not data:
            break
        issues.extend(_summarize_issue(i) for i in data if "pull_request" not in i)
        if len(data) < 100:
            break
        page += 1
    return issues[:limit]


def get_issue(repo: str, number: int, auth: GitHubAuth) -> dict[str, Any]:
    repo = validate_repo(repo)
    data = _request(f"/repos/{repo}/issues/{int(number)}", auth)
    if "pull_request" in data:
        raise GitHubError(f"#{number} is a pull request, not an issue.", 400)
    return _summarize_issue(data)


def get_issue_comments(repo: str, number: int, auth: GitHubAuth) -> list[dict[str, str]]:
    repo = validate_repo(repo)
    data = _request(f"/repos/{repo}/issues/{int(number)}/comments", auth, {"per_page": MAX_COMMENTS})
    if not isinstance(data, list):
        return []
    return [
        {"author": (c.get("user") or {}).get("login", ""), "body": c.get("body") or ""}
        for c in data[:MAX_COMMENTS]
    ]


def source_marker(issue_url: str) -> str:
    """Line appended to imported features; also used to detect duplicates."""
    return f"Source: {issue_url}"


def _clean(text: str) -> str:
    return _HTML_COMMENT_RE.sub("", text).replace("\r\n", "\n").strip()


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 15].rstrip() + "\n…(truncated)"


def issue_to_feature(
    repo: str, issue: dict[str, Any], comments: list[dict[str, str]] | None = None
) -> dict[str, Any]:
    """Convert a GitHub issue (and optional comments) into feature fields."""
    number = issue["number"]
    title = issue["title"].strip() or f"Issue {number}"
    body = _clean(issue.get("body") or "")

    labels = [lbl for lbl in issue.get("labels", []) if lbl]
    category = (labels[0] if labels else DEFAULT_CATEGORY)[:MAX_CATEGORY_CHARS]

    name = f"#{number} {title}"[:MAX_NAME_CHARS]

    parts = [_truncate(body, MAX_BODY_CHARS) if body else title]
    if comments:
        rendered = []
        for c in comments:
            text = _clean(c.get("body", ""))
            if text:
                rendered.append(f"@{c.get('author') or 'unknown'}: {_truncate(text, MAX_COMMENT_CHARS)}")
        if rendered:
            parts.append("Discussion from the issue:\n" + "\n\n".join(rendered))

    footer = f"Imported from GitHub issue {repo}#{number}.\n{source_marker(issue['url'])}"
    description = _truncate("\n\n".join(parts), MAX_DESCRIPTION_CHARS - len(footer) - 2) + "\n\n" + footer

    steps = [m.group("text") for m in _TASK_RE.finditer(body)]
    if not steps:
        steps = [
            f"Read GitHub issue #{number} (description above) and implement the requested change",
            "Verify the change works as described in the issue",
        ]

    return {"category": category, "name": name, "description": description, "steps": steps}
