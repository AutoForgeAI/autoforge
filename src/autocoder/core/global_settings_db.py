"""
Global Settings Database
=======================

Persists **non-secret** application-wide settings in a SQLite database.

This is used for UI-configurable "advanced settings" so users don't need to edit
shell env vars or JSON files repeatedly. Secrets (API keys/tokens) should remain
in environment variables unless a secure store is explicitly implemented.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _settings_db_path() -> Path:
    override = (os.getenv("AUTOCODER_SETTINGS_DB_PATH") or "").strip()
    if override:
        p = Path(override).expanduser()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    d = Path.home() / ".autocoder"
    d.mkdir(parents=True, exist_ok=True)
    return d / "settings.db"


def _connect() -> sqlite3.Connection:
    path = _settings_db_path()
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS global_settings (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    return conn


def get_global_setting_json(key: str) -> dict[str, Any] | None:
    key = (key or "").strip()
    if not key:
        return None
    with _connect() as conn:
        row = conn.execute("SELECT value_json FROM global_settings WHERE key = ?", (key,)).fetchone()
    if not row:
        return None
    try:
        val = json.loads(row[0])
        return val if isinstance(val, dict) else None
    except Exception:
        return None


def set_global_setting_json(key: str, value: dict[str, Any]) -> None:
    key = (key or "").strip()
    if not key:
        raise ValueError("key is required")
    if not isinstance(value, dict):
        raise TypeError("value must be a dict")
    payload = json.dumps(value, ensure_ascii=False)
    ts = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO global_settings(key, value_json, updated_at)
            VALUES(?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value_json = excluded.value_json,
                updated_at = excluded.updated_at
            """,
            (key, payload, ts),
        )
        conn.commit()

