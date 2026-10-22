"""
Shared Environment Variable Constants
======================================

Single source of truth for environment variables forwarded to Claude CLI
subprocesses.  Imported by both ``client.py`` (agent sessions) and
``server/services/chat_constants.py`` (chat sessions) to avoid maintaining
duplicate lists.

These allow autoforge to use alternative API endpoints (Ollama, GLM,
Vertex AI) without affecting the user's global Claude Code settings.

Also provides ``find_claude_cli()``, the shared lookup for the system Claude
CLI executable used by agent and chat sessions.
"""

import os
import shutil
import sys
from pathlib import Path

API_ENV_VARS: list[str] = [
    # Core API configuration
    "ANTHROPIC_BASE_URL",              # Custom API endpoint (e.g., https://api.z.ai/api/anthropic)
    "ANTHROPIC_AUTH_TOKEN",            # API authentication token
    "ANTHROPIC_API_KEY",               # API key (used by Kimi and other providers)
    "API_TIMEOUT_MS",                  # Request timeout in milliseconds
    # Model tier overrides
    "ANTHROPIC_DEFAULT_SONNET_MODEL",  # Model override for Sonnet
    "ANTHROPIC_DEFAULT_OPUS_MODEL",    # Model override for Opus
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",   # Model override for Haiku
    # Vertex AI configuration
    "CLAUDE_CODE_USE_VERTEX",          # Enable Vertex AI mode (set to "1")
    "CLOUD_ML_REGION",                 # GCP region (e.g., us-east5)
    "ANTHROPIC_VERTEX_PROJECT_ID",     # GCP project ID
]


# Environment variables that can point at the Claude CLI executable explicitly.
# Useful when auto-detection fails (e.g. Windows usernames containing spaces,
# or a non-standard npm prefix).
CLAUDE_CLI_ENV_VARS: list[str] = ["CLAUDE_CLI_PATH", "CLAUDE_PATH"]


def _clean_path_value(value: str) -> str:
    """Strip whitespace and surrounding quotes (e.g. from Windows "Copy as path")."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        value = value[1:-1].strip()
    return os.path.expandvars(os.path.expanduser(value))


def find_claude_cli() -> str | None:
    """
    Locate the system Claude CLI executable.

    Resolution order:
    1. ``CLAUDE_CLI_PATH`` / ``CLAUDE_PATH`` environment variables (a file path,
       or a command name resolved via PATH)
    2. ``claude`` on PATH
    3. Common npm global install locations (Windows ``%APPDATA%\\npm``,
       ``~/.npm-global/bin``, ``~/.local/bin``, ``~/.claude/local``)

    Paths containing spaces are returned as-is; callers pass them to
    subprocess as a single argv element, so no extra quoting is needed.

    Returns:
        Absolute path to the CLI, or None if it cannot be found.
    """
    for var in CLAUDE_CLI_ENV_VARS:
        raw = os.environ.get(var)
        if not raw or not raw.strip():
            continue
        candidate = _clean_path_value(raw)
        if Path(candidate).is_file():
            return str(Path(candidate))
        found = shutil.which(candidate)
        if found:
            return found

    found = shutil.which("claude")
    if found:
        return found

    candidates: list[Path] = []
    home = Path.home()
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        npm_dirs = [Path(appdata) / "npm"] if appdata else []
        npm_dirs.append(home / "AppData" / "Roaming" / "npm")
        for npm_dir in npm_dirs:
            candidates.extend(npm_dir / name for name in ("claude.cmd", "claude.exe"))
        candidates.append(home / ".local" / "bin" / "claude.exe")
    else:
        candidates.extend([
            home / ".npm-global" / "bin" / "claude",
            home / ".local" / "bin" / "claude",
            home / ".claude" / "local" / "claude",
        ])

    for path in candidates:
        if path.is_file():
            return str(path)

    return None
