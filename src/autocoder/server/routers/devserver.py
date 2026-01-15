"""
Dev Server Router
=================

Start/stop/status for a per-project dev server, plus a dedicated WebSocket stream.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, WebSocket
from fastapi.websockets import WebSocketDisconnect
from pydantic import BaseModel, Field

from autocoder.agent.registry import get_project_path
from ..services.dev_server_manager import get_dev_server_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_name}/devserver", tags=["devserver"])


def _validate_project_name(name: str) -> None:
    if not re.match(r"^[a-zA-Z0-9_-]{1,50}$", name):
        raise HTTPException(status_code=400, detail="Invalid project name")


def _project_dir(project_name: str) -> Path:
    _validate_project_name(project_name)
    p = get_project_path(project_name)
    if not p:
        raise HTTPException(status_code=404, detail="Project not found in registry")
    d = Path(p).resolve()
    if not d.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")
    return d


class DevServerStatusResponse(BaseModel):
    status: str
    pid: int | None = None
    started_at: datetime | None = None
    command: str | None = None
    url: str | None = None
    api_port: int | None = None
    web_port: int | None = None


class DevServerStartRequest(BaseModel):
    command: str | None = Field(default=None, description="Override dev server command (shell)")
    api_port: int | None = Field(default=None, ge=1024, le=65535)
    web_port: int | None = Field(default=None, ge=1024, le=65535)


class DevServerActionResponse(BaseModel):
    success: bool
    status: str
    message: str = ""
    url: str | None = None


@router.get("/status", response_model=DevServerStatusResponse)
async def get_devserver_status(project_name: str) -> DevServerStatusResponse:
    d = _project_dir(project_name)
    mgr = get_dev_server_manager(project_name, d)
    await mgr.healthcheck()
    return DevServerStatusResponse(**mgr.get_status_dict())


@router.post("/start", response_model=DevServerActionResponse)
async def start_devserver(project_name: str, req: DevServerStartRequest = DevServerStartRequest()) -> DevServerActionResponse:
    d = _project_dir(project_name)
    mgr = get_dev_server_manager(project_name, d)
    ok, msg = await mgr.start(command=req.command, api_port=req.api_port, web_port=req.web_port)
    return DevServerActionResponse(success=ok, status=mgr.status, message=msg, url=mgr.url)


@router.post("/stop", response_model=DevServerActionResponse)
async def stop_devserver(project_name: str) -> DevServerActionResponse:
    d = _project_dir(project_name)
    mgr = get_dev_server_manager(project_name, d)
    ok, msg = await mgr.stop()
    return DevServerActionResponse(success=ok, status=mgr.status, message=msg, url=mgr.url)


async def devserver_websocket(websocket: WebSocket, project_name: str) -> None:
    """
    WebSocket endpoint: `/ws/projects/{project_name}/devserver`

    Streams:
    - devserver_status
    - devserver_log
    """
    if not re.match(r"^[a-zA-Z0-9_-]{1,50}$", project_name):
        await websocket.close(code=4000, reason="Invalid project name")
        return

    try:
        project_dir = _project_dir(project_name)
    except HTTPException as e:
        await websocket.close(code=4004, reason=str(e.detail))
        return

    mgr = get_dev_server_manager(project_name, project_dir)

    await websocket.accept()

    async def send_status() -> None:
        await websocket.send_json(
            {
                "type": "devserver_status",
                "status": mgr.status,
                "pid": mgr.pid,
                "started_at": mgr.started_at.isoformat() if mgr.started_at else None,
                "command": mgr.command,
                "url": mgr.url,
                "api_port": mgr.api_port,
                "web_port": mgr.web_port,
            }
        )

    async def on_output(line: str) -> None:
        await websocket.send_json(
            {"type": "devserver_log", "line": line, "timestamp": datetime.now().isoformat()}
        )

    async def on_status_change(status: str) -> None:
        await send_status()

    # Register callbacks
    mgr.add_output_callback(on_output)
    mgr.add_status_callback(on_status_change)

    try:
        # Initial state + tail
        await send_status()
        for line in mgr.tail():
            await websocket.send_json(
                {"type": "devserver_log", "line": line, "timestamp": datetime.now().isoformat()}
            )

        while True:
            # keep alive; ignore incoming for now
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except Exception:
                await asyncio.sleep(0.1)
    finally:
        mgr.remove_output_callback(on_output)
        mgr.remove_status_callback(on_status_change)
