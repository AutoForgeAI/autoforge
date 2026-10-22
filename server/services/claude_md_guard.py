"""
CLAUDE.md Guard
===============

Chat sessions (spec creation, assistant) pass their system prompt to the
Claude CLI by writing it to ``<project>/CLAUDE.md``. For projects onboarded
from an existing codebase that file usually belongs to the user, so it must
not be lost.

``write_session_claude_md`` backs up a pre-existing CLAUDE.md to
``.autoforge/CLAUDE.md.user-backup`` before overwriting it, and
``release_session_claude_md`` restores it once the last holder releases.
Sessions only hold CLAUDE.md while the Claude CLI is starting or answering a
turn, so the user's file is back in place between turns, after a WebSocket
disconnect and when the server stops. A backup left behind by a crash is never
overwritten; ``restore_leftover_claude_md`` puts it back (e.g. before an agent
run) and so does the next session that releases.
"""

import logging
import os
import shutil
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

BACKUP_NAME = "CLAUDE.md.user-backup"

_lock = threading.Lock()
# Number of open sessions per project dir that currently own CLAUDE.md
_active_sessions: dict[str, int] = {}


def get_claude_md_backup_path(project_dir: Path) -> Path:
    """Path where the user's own CLAUDE.md is kept while a chat session runs."""
    return project_dir / ".autoforge" / BACKUP_NAME


def write_session_claude_md(project_dir: Path, content: str) -> None:
    """
    Write a session system prompt to ``project_dir/CLAUDE.md``, backing up the
    user's file first. Every call must be paired with
    ``release_session_claude_md``.
    """
    key = str(project_dir.resolve())
    claude_md = project_dir / "CLAUDE.md"
    backup = get_claude_md_backup_path(project_dir)
    with _lock:
        if _active_sessions.get(key, 0) == 0 and claude_md.exists() and not backup.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(claude_md, backup)
            logger.info(f"Backed up existing {claude_md} to {backup}")
        _active_sessions[key] = _active_sessions.get(key, 0) + 1
        claude_md.write_text(content, encoding="utf-8")


def release_session_claude_md(project_dir: Path) -> None:
    """Release a session's hold on CLAUDE.md; the last one restores the user's file."""
    key = str(project_dir.resolve())
    with _lock:
        count = _active_sessions.get(key, 0)
        if count <= 0:
            return
        if count > 1:
            _active_sessions[key] = count - 1
            return
        del _active_sessions[key]
        backup = get_claude_md_backup_path(project_dir)
        if backup.exists():
            try:
                os.replace(backup, project_dir / "CLAUDE.md")
                logger.info(f"Restored user's CLAUDE.md in {project_dir}")
            except OSError as e:
                logger.warning(f"Could not restore CLAUDE.md from {backup}: {e}")


def restore_leftover_claude_md(project_dir: Path) -> bool:
    """
    Put back a user CLAUDE.md left in the backup by a session that never released
    (crash, killed server). Skipped while a chat session is mid-turn, since it
    still needs its prompt; that session restores the file when it releases.

    Returns True if a backup was restored.
    """
    key = str(project_dir.resolve())
    backup = get_claude_md_backup_path(project_dir)
    with _lock:
        if _active_sessions.get(key, 0) > 0 or not backup.exists():
            return False
        try:
            os.replace(backup, project_dir / "CLAUDE.md")
        except OSError as e:
            logger.warning(f"Could not restore CLAUDE.md from {backup}: {e}")
            return False
    logger.info(f"Restored leftover user CLAUDE.md in {project_dir}")
    return True
