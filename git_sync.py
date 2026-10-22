"""
Git Remote Sync
===============

Optional "auto-push" support: after a coding agent session finishes
successfully, push the project's current branch to its git remote so work
shows up on GitHub (or any other remote) without manual intervention.

Disabled by default. Enable it either with the "Auto-push to Git Remote"
toggle in the Settings UI (stored in the registry as ``git_auto_push``) or by
setting ``AUTOFORGE_GIT_AUTO_PUSH=1`` in the environment.

Safety rules:
- Never force-pushes.
- Never creates remotes or repositories; if the branch has no upstream and
  there is no ``origin`` remote, the push is skipped.
- Skips when HEAD is detached.
- Runs non-interactively (no credential prompts) with a timeout, so a
  misconfigured remote can never hang the orchestrator.
"""

import logging
import os
import subprocess
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

GIT_AUTO_PUSH_SETTING = "git_auto_push"
GIT_AUTO_PUSH_ENV = "AUTOFORGE_GIT_AUTO_PUSH"
PUSH_TIMEOUT_SECONDS = 60

# Serializes pushes when several agents finish at the same time
_push_lock = threading.Lock()


def _parse_bool(value: str | None) -> bool | None:
    if value is None or value.strip() == "":
        return None
    return value.strip().lower() in ("1", "true", "yes", "on")


def is_auto_push_enabled() -> bool:
    """Return True if auto-push is enabled (env var overrides the UI setting)."""
    env_value = _parse_bool(os.environ.get(GIT_AUTO_PUSH_ENV))
    if env_value is not None:
        return env_value

    try:
        from registry import get_setting
        return _parse_bool(get_setting(GIT_AUTO_PUSH_SETTING, "false")) or False
    except Exception as e:  # registry unavailable - treat as disabled
        logger.debug("Could not read %s setting: %s", GIT_AUTO_PUSH_SETTING, e)
        return False


def _git(project_dir: Path, *args: str, timeout: float = 15) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        # Fail fast instead of waiting for a username/password prompt
        "GIT_TERMINAL_PROMPT": "0",
        "GCM_INTERACTIVE": "never",
    }
    return subprocess.run(
        ["git", *args],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=timeout,
        stdin=subprocess.DEVNULL,
        env=env,
    )


def push_current_branch(project_dir: Path) -> tuple[bool, str]:
    """Push the current branch of ``project_dir`` to its remote.

    Uses the branch's upstream if one is configured, otherwise pushes to
    ``origin`` and sets it as upstream.

    Returns:
        (success, message) - success is False when the push was skipped or failed.
    """
    with _push_lock:
        try:
            inside = _git(project_dir, "rev-parse", "--is-inside-work-tree")
            if inside.returncode != 0 or inside.stdout.strip() != "true":
                return False, "not a git repository, skipping push"

            branch_res = _git(project_dir, "symbolic-ref", "--quiet", "--short", "HEAD")
            branch = branch_res.stdout.strip()
            if branch_res.returncode != 0 or not branch:
                return False, "detached HEAD, skipping push"

            upstream = _git(
                project_dir, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"
            )
            if upstream.returncode == 0 and upstream.stdout.strip():
                target = upstream.stdout.strip()
                push_args = ["push"]
            else:
                remotes = _git(project_dir, "remote").stdout.split()
                if "origin" not in remotes:
                    return False, f"branch '{branch}' has no upstream and no 'origin' remote is configured, skipping push"
                target = f"origin/{branch}"
                push_args = ["push", "--set-upstream", "origin", branch]

            result = _git(project_dir, *push_args, timeout=PUSH_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            return False, f"git push timed out after {PUSH_TIMEOUT_SECONDS}s"
        except (FileNotFoundError, OSError) as e:
            return False, f"git unavailable: {e}"

        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip().splitlines()
            reason = detail[-1] if detail else f"exit code {result.returncode}"
            return False, f"git push to {target} failed: {reason}"
        return True, f"pushed '{branch}' to {target}"
