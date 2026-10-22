"""
Git Remote Sync
===============

Optional "auto-push" support: after an agent session finishes, push the
project's current branch to its Git remote so work shows up on GitHub (or any
other Git host) without manual intervention.

The feature is opt-in via the global ``git_auto_push`` setting and is
deliberately conservative:

- It never creates repositories, remotes or branches on the host. The user
  sets up the remote once (e.g. ``gh repo create --source . --push``) and picks
  the branch to work on (e.g. ``git checkout -b feature/x``).
- It never force-pushes.
- Failures (no remote, auth problems, network errors, rejected pushes) are
  reported and swallowed so they can never break the agent loop.
"""

import os
import subprocess
from pathlib import Path

GIT_AUTO_PUSH_SETTING = "git_auto_push"
PUSH_TIMEOUT_SECONDS = 120


def is_auto_push_enabled() -> bool:
    """Return True when the global ``git_auto_push`` setting is on."""
    try:
        from registry import get_setting
    except Exception:
        return False
    return (get_setting(GIT_AUTO_PUSH_SETTING, "false") or "false").lower() == "true"


def _git(project_dir: Path, *args: str, timeout: int = 30) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    # Never block on an interactive credential prompt - fail fast instead.
    env["GIT_TERMINAL_PROMPT"] = "0"
    env.setdefault("GCM_INTERACTIVE", "never")
    return subprocess.run(
        ["git", *args],
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        stdin=subprocess.DEVNULL,
    )


def push_to_remote(project_dir: Path) -> tuple[bool, str]:
    """
    Push the project's current branch to its remote.

    If the branch already tracks an upstream, a plain ``git push`` is used.
    Otherwise the branch is pushed to ``origin`` (or the only configured
    remote) and set as upstream.

    Returns:
        (success, message) - message is a human-readable summary for logs.
    """
    try:
        inside = _git(project_dir, "rev-parse", "--is-inside-work-tree")
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return False, "not a git repository"

        branch = _git(project_dir, "symbolic-ref", "--quiet", "--short", "HEAD")
        if branch.returncode != 0 or not branch.stdout.strip():
            return False, "HEAD is detached; check out a branch to enable auto-push"
        branch_name = branch.stdout.strip()

        has_commit = _git(project_dir, "rev-parse", "--verify", "--quiet", "HEAD")
        if has_commit.returncode != 0:
            return False, "no commits to push yet"

        upstream = _git(project_dir, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
        if upstream.returncode == 0 and upstream.stdout.strip():
            push_args = ["push"]
            target = upstream.stdout.strip()
        else:
            remotes = [r for r in _git(project_dir, "remote").stdout.split() if r]
            if not remotes:
                return False, "no git remote configured (e.g. run: gh repo create --source . --push)"
            remote = "origin" if "origin" in remotes else remotes[0]
            if remote != "origin" and len(remotes) > 1:
                return False, "multiple remotes and no 'origin'; set an upstream with git push -u"
            push_args = ["push", "--set-upstream", remote, branch_name]
            target = f"{remote}/{branch_name}"

        result = _git(project_dir, *push_args, timeout=PUSH_TIMEOUT_SECONDS)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip().splitlines()
            return False, f"push to {target} failed: {detail[-1] if detail else 'unknown error'}"
        return True, f"pushed {branch_name} to {target}"
    except FileNotFoundError:
        return False, "git executable not found"
    except subprocess.TimeoutExpired:
        return False, "git push timed out"
    except Exception as e:  # pragma: no cover - defensive, must never break the agent loop
        return False, f"unexpected error: {e}"


def maybe_push_to_remote(project_dir: Path) -> None:
    """Push to the remote if auto-push is enabled, printing the outcome."""
    if not is_auto_push_enabled():
        return
    ok, message = push_to_remote(project_dir)
    if ok:
        print(f"[git auto-push] {message}", flush=True)
    else:
        print(f"[git auto-push] skipped: {message}", flush=True)
