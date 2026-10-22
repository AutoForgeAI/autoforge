"""
Claude CLI Discovery
====================

Single place to locate the Claude Code CLI executable used by agent and chat
sessions (and reported by the setup status endpoint).

Resolution order:
1. ``CLAUDE_PATH`` (or ``CLAUDE_CLI_PATH``) environment variable - an explicit
   override for setups where PATH lookup fails. Surrounding quotes are
   stripped so values such as ``"C:\\Users\\OXFAM MONS\\AppData\\Roaming\\npm\\claude.cmd"``
   work even though the path contains spaces.
2. ``shutil.which("claude")`` - the normal PATH lookup.
3. Well-known install locations (npm global prefix, native installer), so the
   CLI is still found when it is installed but PATH was not updated.
"""

import logging
import os
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

CLAUDE_PATH_ENV_VARS = ("CLAUDE_PATH", "CLAUDE_CLI_PATH")


def _clean_path_value(value: str) -> str:
    """Strip whitespace and matching surrounding quotes from a path value."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1].strip()
    return os.path.expandvars(os.path.expanduser(value))


def _is_executable_file(path: Path) -> bool:
    try:
        return path.is_file() and (sys.platform == "win32" or os.access(path, os.X_OK))
    except OSError:
        return False


def _candidate_install_paths() -> list[Path]:
    """Common Claude CLI install locations, used when PATH lookup fails."""
    home = Path.home()
    candidates: list[Path] = []
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidates.append(Path(appdata) / "npm" / "claude.cmd")
        candidates.append(home / "AppData" / "Roaming" / "npm" / "claude.cmd")
        candidates.append(home / ".local" / "bin" / "claude.exe")
    else:
        candidates.append(home / ".local" / "bin" / "claude")
        candidates.append(home / ".claude" / "local" / "claude")
        candidates.append(home / ".npm-global" / "bin" / "claude")
    return candidates


def find_claude_cli() -> str | None:
    """Return the path to the Claude CLI executable, or None if not found."""
    for var in CLAUDE_PATH_ENV_VARS:
        raw = os.environ.get(var)
        if not raw or not raw.strip():
            continue
        configured = _clean_path_value(raw)
        candidate = Path(configured)
        if _is_executable_file(candidate):
            return str(candidate)
        # Allow a bare command name (e.g. CLAUDE_PATH=claude-dev) resolved via PATH
        found = shutil.which(configured)
        if found:
            return found
        logger.warning("%s is set to %r but no executable was found there; falling back to PATH", var, raw)

    found = shutil.which("claude")
    if found:
        return found

    for candidate in _candidate_install_paths():
        if _is_executable_file(candidate):
            return str(candidate)

    return None
