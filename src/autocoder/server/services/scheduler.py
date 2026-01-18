"""
Run Scheduler
=============

Lightweight in-process scheduler for delayed agent starts.
Persists scheduled runs in the global settings DB so UI restarts do not lose them.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from autocoder.core.global_settings_db import get_global_setting_json, set_global_setting_json
from autocoder.agent.registry import get_project_path
from .process_manager import get_manager, AgentProcessManager

logger = logging.getLogger(__name__)

_SCHEDULE_KEY = "scheduled_runs_v1"


@dataclass
class ScheduledRun:
    project_name: str
    run_at: datetime
    created_at: datetime
    request: dict[str, Any]
    task: asyncio.Task | None = None


_lock = threading.Lock()
_scheduled: dict[str, ScheduledRun] = {}


def _serialize(run: ScheduledRun) -> dict[str, Any]:
    return {
        "project_name": run.project_name,
        "run_at": run.run_at.isoformat(),
        "created_at": run.created_at.isoformat(),
        "request": dict(run.request or {}),
    }


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _load_persisted() -> dict[str, dict[str, Any]]:
    data = get_global_setting_json(_SCHEDULE_KEY)
    if isinstance(data, dict):
        return {str(k): v for k, v in data.items() if isinstance(v, dict)}
    return {}


def _persist_all() -> None:
    with _lock:
        payload = {name: _serialize(run) for name, run in _scheduled.items()}
    try:
        set_global_setting_json(_SCHEDULE_KEY, payload)
    except Exception as exc:
        logger.debug(f"Failed to persist schedules: {exc}")


def get_schedule(project_name: str) -> ScheduledRun | None:
    with _lock:
        return _scheduled.get(project_name)


def cancel_schedule(project_name: str) -> bool:
    run: ScheduledRun | None = None
    with _lock:
        run = _scheduled.pop(project_name, None)
    if run and run.task and not run.task.done():
        run.task.cancel()
    if run:
        _persist_all()
        return True
    return False


async def schedule_run(
    manager: AgentProcessManager,
    run_at: datetime,
    request: dict[str, Any],
) -> ScheduledRun:
    if run_at.tzinfo is not None:
        run_at = run_at.astimezone().replace(tzinfo=None)
    project_name = manager.project_name
    cancel_schedule(project_name)
    created_at = datetime.now()

    async def _runner() -> None:
        try:
            delay = max(0.0, (run_at - datetime.now()).total_seconds())
            if delay:
                await asyncio.sleep(delay)

            if manager.status in {"running", "paused"}:
                logger.info(f"⏱️ Scheduled run skipped; {project_name} already {manager.status}")
                return

            ok, msg = await manager.start(
                yolo_mode=bool(request.get("yolo_mode", False)),
                parallel_mode=bool(request.get("parallel_mode", False)),
                parallel_count=int(request.get("parallel_count", 3) or 3),
                model_preset=str(request.get("model_preset", "balanced") or "balanced"),
            )
            if not ok:
                logger.warning(f"⏱️ Scheduled run failed for {project_name}: {msg}")
        except asyncio.CancelledError:
            return
        finally:
            with _lock:
                _scheduled.pop(project_name, None)
            _persist_all()

    task = asyncio.create_task(_runner())
    run = ScheduledRun(
        project_name=project_name,
        run_at=run_at,
        created_at=created_at,
        request=dict(request or {}),
        task=task,
    )

    with _lock:
        _scheduled[project_name] = run
    _persist_all()
    return run


async def restore_schedules() -> None:
    data = _load_persisted()
    if not data:
        return

    for project_name, payload in data.items():
        run_at = _parse_dt(str(payload.get("run_at") or ""))
        created_at = _parse_dt(str(payload.get("created_at") or "")) or datetime.now()
        req = payload.get("request") or {}
        if not isinstance(req, dict):
            req = {}
        if not run_at:
            continue
        if run_at.tzinfo is not None:
            run_at = run_at.astimezone().replace(tzinfo=None)

        project_path = get_project_path(project_name)
        if not project_path:
            logger.warning(f"Skipping schedule restore; project not found: {project_name}")
            continue

        manager = get_manager(project_name, Path(project_path), Path(__file__).resolve().parents[2])
        # Re-schedule from persisted data (run_at may be in the past -> run immediately).
        await schedule_run(manager, run_at, req)


async def cleanup_schedules() -> None:
    with _lock:
        runs = list(_scheduled.values())
        _scheduled.clear()
    for run in runs:
        if run.task and not run.task.done():
            run.task.cancel()
    _persist_all()
