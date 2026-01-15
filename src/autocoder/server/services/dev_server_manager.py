"""
Dev Server Manager
==================

Manage a per-project "dev server" subprocess (e.g. `npm run dev`) from the UI.

This is intentionally lightweight and framework-agnostic:
- If `autocoder.yaml` defines `commands.dev`, that command is used.
- Otherwise, for Node projects we auto-detect a dev command from package.json scripts.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import re
import subprocess
import threading
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable, Literal, Set

import psutil

from autocoder.core.project_config import load_project_config

from .process_manager import sanitize_output

logger = logging.getLogger(__name__)

DevServerStatus = Literal["stopped", "running", "crashed"]

_URL_RE = re.compile(
    r"(https?://(?:localhost|127\.0\.0\.1|\[::1\])(?::\d{2,5})?(?:/[^\s]*)?)",
    re.IGNORECASE,
)


def detect_dev_command(project_dir: Path) -> str | None:
    """
    Best-effort dev command detection for common stacks.

    Priority:
    1) autocoder.yaml commands.dev
    2) Node package.json scripts (dev/start/serve/preview)
    """
    project_dir = Path(project_dir).resolve()

    try:
        cfg = load_project_config(project_dir)
        dev = cfg.get_command("dev")
        if dev and dev.command.strip():
            return dev.command.strip()
    except Exception:
        # If autocoder.yaml is invalid, fall back to package.json detection.
        pass

    pkg = project_dir / "package.json"
    if not pkg.exists():
        return None

    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except Exception:
        return None

    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        return None

    for key, cmd in (
        ("dev", "npm run dev"),
        ("start", "npm start"),
        ("serve", "npm run serve"),
        ("preview", "npm run preview"),
    ):
        if key in scripts:
            return cmd

    return None


def extract_url(text: str) -> str | None:
    """Extract the first localhost URL from a line of output."""
    m = _URL_RE.search(text or "")
    if not m:
        return None
    url = (m.group(1) or "").strip()
    return url or None


class DevServerManager:
    """
    Manage a dev server subprocess for a single project, with log streaming callbacks.
    """

    MAX_LOG_LINES = 500

    def __init__(self, project_name: str, project_dir: Path):
        self.project_name = project_name
        self.project_dir = Path(project_dir).resolve()

        self.process: subprocess.Popen | None = None
        self._status: DevServerStatus = "stopped"
        self.started_at: datetime | None = None
        self.command: str | None = None
        self.url: str | None = None
        self.api_port: int | None = None
        self.web_port: int | None = None

        self._output_task: asyncio.Task | None = None
        self._output_callbacks: Set[Callable[[str], Awaitable[None]]] = set()
        self._status_callbacks: Set[Callable[[DevServerStatus], Awaitable[None]]] = set()
        self._callbacks_lock = threading.Lock()

        self._tail: deque[str] = deque(maxlen=self.MAX_LOG_LINES)

        # Lock file stored inside the project directory
        self.lock_file = self.project_dir / ".devserver.lock"

    @property
    def status(self) -> DevServerStatus:
        return self._status

    @status.setter
    def status(self, value: DevServerStatus) -> None:
        old = self._status
        self._status = value
        if old != value:
            self._notify_status_change(value)

    @property
    def pid(self) -> int | None:
        return self.process.pid if self.process else None

    def add_output_callback(self, cb: Callable[[str], Awaitable[None]]) -> None:
        with self._callbacks_lock:
            self._output_callbacks.add(cb)

    def remove_output_callback(self, cb: Callable[[str], Awaitable[None]]) -> None:
        with self._callbacks_lock:
            self._output_callbacks.discard(cb)

    def add_status_callback(self, cb: Callable[[DevServerStatus], Awaitable[None]]) -> None:
        with self._callbacks_lock:
            self._status_callbacks.add(cb)

    def remove_status_callback(self, cb: Callable[[DevServerStatus], Awaitable[None]]) -> None:
        with self._callbacks_lock:
            self._status_callbacks.discard(cb)

    def tail(self) -> list[str]:
        return list(self._tail)

    def _check_lock(self) -> bool:
        if not self.lock_file.exists():
            return True
        try:
            pid = int(self.lock_file.read_text(encoding="utf-8").strip())
        except Exception:
            self.lock_file.unlink(missing_ok=True)
            return True

        if psutil.pid_exists(pid):
            # If the PID still exists, assume the dev server is still running.
            return False

        # stale lock
        self.lock_file.unlink(missing_ok=True)
        return True

    def _create_lock(self) -> None:
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        if self.process:
            self.lock_file.write_text(str(self.process.pid), encoding="utf-8")

    def _remove_lock(self) -> None:
        self.lock_file.unlink(missing_ok=True)

    async def _safe_callback(self, cb: Callable, *args) -> None:
        try:
            await cb(*args)
        except Exception as e:
            logger.debug(f"Dev server callback error: {e}")

    async def _broadcast_output(self, line: str) -> None:
        with self._callbacks_lock:
            callbacks = list(self._output_callbacks)
        for cb in callbacks:
            await self._safe_callback(cb, line)

    def _notify_status_change(self, status: DevServerStatus) -> None:
        with self._callbacks_lock:
            callbacks = list(self._status_callbacks)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        for cb in callbacks:
            loop.create_task(self._safe_callback(cb, status))

    async def _stream_output(self) -> None:
        if not self.process or not self.process.stdout:
            return
        try:
            loop = asyncio.get_running_loop()
            while True:
                line = await loop.run_in_executor(None, self.process.stdout.readline)
                if not line:
                    break
                decoded = line.decode("utf-8", errors="replace").rstrip()
                sanitized = sanitize_output(decoded)

                self._tail.append(sanitized)
                url = extract_url(sanitized)
                if url:
                    self.url = url

                await self._broadcast_output(sanitized)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning(f"Dev server output streaming error: {e}")
        finally:
            if self.process and self.process.poll() is not None:
                if self.status == "running":
                    self.status = "crashed" if self.process.returncode else "stopped"
                self._remove_lock()

    async def start(
        self,
        *,
        command: str | None = None,
        api_port: int | None = None,
        web_port: int | None = None,
    ) -> tuple[bool, str]:
        if self.status == "running":
            return False, "Dev server is already running"

        if not self._check_lock():
            return False, "Another dev server instance is already running for this project"

        resolved_cmd = (command or "").strip() or detect_dev_command(self.project_dir)
        if not resolved_cmd:
            return (
                False,
                "No dev server command detected. Add `commands.dev` in autocoder.yaml or a package.json dev/start script.",
            )

        env = os.environ.copy()
        if api_port is not None:
            env["AUTOCODER_API_PORT"] = str(api_port)
            env.setdefault("PORT", str(api_port))
            self.api_port = api_port
        if web_port is not None:
            env["AUTOCODER_WEB_PORT"] = str(web_port)
            env.setdefault("VITE_PORT", str(web_port))
            self.web_port = web_port

        try:
            self.command = resolved_cmd
            self.url = None
            self.api_port = api_port
            self.web_port = web_port

            self.process = subprocess.Popen(
                resolved_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=str(self.project_dir),
                env=env,
            )
            self.started_at = datetime.now()
            self.status = "running"
            self._create_lock()
            self._output_task = asyncio.create_task(self._stream_output())
            return True, f"Dev server started with PID {self.process.pid}"
        except Exception as e:
            logger.exception("Failed to start dev server")
            self.process = None
            self.status = "stopped"
            return False, f"Failed to start dev server: {e}"

    async def stop(self) -> tuple[bool, str]:
        if not self.process or self.status == "stopped":
            return False, "Dev server is not running"

        try:
            if self._output_task:
                self._output_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._output_task
                self._output_task = None

            self.process.terminate()
            loop = asyncio.get_running_loop()
            try:
                await asyncio.wait_for(loop.run_in_executor(None, self.process.wait), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await loop.run_in_executor(None, self.process.wait)

            self.process = None
            self.status = "stopped"
            self.started_at = None
            self.command = None
            self.url = None
            self.api_port = None
            self.web_port = None
            self._remove_lock()
            return True, "Dev server stopped"
        except Exception as e:
            logger.exception("Failed to stop dev server")
            return False, f"Failed to stop dev server: {e}"

    async def healthcheck(self) -> bool:
        if not self.process:
            return self.status == "stopped"
        poll = self.process.poll()
        if poll is not None:
            if self.status == "running":
                self.status = "crashed"
                self._remove_lock()
            return False
        return True

    def get_status_dict(self) -> dict:
        return {
            "status": self.status,
            "pid": self.pid,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "command": self.command,
            "url": self.url,
            "api_port": self.api_port,
            "web_port": self.web_port,
        }


_dev_managers: dict[str, DevServerManager] = {}
_dev_lock = threading.Lock()


def get_dev_server_manager(project_name: str, project_dir: Path) -> DevServerManager:
    with _dev_lock:
        if project_name not in _dev_managers:
            _dev_managers[project_name] = DevServerManager(project_name, project_dir)
        return _dev_managers[project_name]


async def cleanup_all_dev_servers() -> None:
    with _dev_lock:
        managers = list(_dev_managers.values())
        _dev_managers.clear()
    for m in managers:
        with contextlib.suppress(Exception):
            if m.status == "running":
                await m.stop()
