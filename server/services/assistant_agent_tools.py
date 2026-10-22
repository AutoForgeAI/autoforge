"""
Assistant Agent Control Tools
=============================

In-process MCP server that lets the project assistant check and control the
coding agent (status/start/stop/pause/resume) for the project it is attached to.

The tools run inside the FastAPI server process and reuse the agent router's
handlers, so they share the same process manager, settings defaults and
scheduler notifications as the UI's agent controls.
"""

import json
import logging
from typing import Any

from claude_agent_sdk import SdkMcpTool, create_sdk_mcp_server, tool
from claude_agent_sdk.types import McpSdkServerConfig
from fastapi import HTTPException
from pydantic import ValidationError

logger = logging.getLogger(__name__)

AGENT_CONTROL_SERVER_NAME = "agent_control"

# Fully-qualified tool names as exposed to the model
AGENT_CONTROL_TOOLS = [
    f"mcp__{AGENT_CONTROL_SERVER_NAME}__agent_get_status",
    f"mcp__{AGENT_CONTROL_SERVER_NAME}__agent_start",
    f"mcp__{AGENT_CONTROL_SERVER_NAME}__agent_stop",
    f"mcp__{AGENT_CONTROL_SERVER_NAME}__agent_pause",
    f"mcp__{AGENT_CONTROL_SERVER_NAME}__agent_resume",
]

AGENT_START_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "yolo_mode": {
            "type": "boolean",
            "description": "Skip browser/regression testing for faster prototyping. Omit to use the global setting.",
        },
        "max_concurrency": {
            "type": "integer",
            "minimum": 1,
            "maximum": 5,
            "description": "Number of concurrent coding agents (1-5). Omit for a single agent.",
        },
    },
    "required": [],
}

EMPTY_SCHEMA: dict[str, Any] = {"type": "object", "properties": {}, "required": []}


def _result(payload: dict[str, Any], is_error: bool = False) -> dict[str, Any]:
    """Format a tool result as MCP text content."""
    result: dict[str, Any] = {"content": [{"type": "text", "text": json.dumps(payload, indent=2)}]}
    if is_error:
        result["is_error"] = True
    return result


def _error(message: str) -> dict[str, Any]:
    return _result({"success": False, "error": message}, is_error=True)


def build_agent_control_tools(project_name: str) -> list[SdkMcpTool[Any]]:
    """Build the agent control tools bound to a single project.

    The project name is captured in the closure rather than taken as a tool
    argument, so the assistant can only control its own project's agent.
    """
    # Imported lazily: the router imports services, so a module-level import
    # here would be circular when the router package is loaded first.
    from ..routers import agent as agent_router
    from ..schemas import AgentStartRequest

    async def _run(action: str, coro_factory) -> dict[str, Any]:
        try:
            response = await coro_factory()
        except HTTPException as e:
            return _error(str(e.detail))
        except Exception as e:
            logger.exception(f"Assistant agent_{action} failed for {project_name}")
            return _error(f"Failed to {action} agent: {e}")
        # mode="json" so datetimes (e.g. AgentStatus.started_at) become ISO strings
        payload = response.model_dump(mode="json")
        return _result(payload, is_error=not payload.get("success", True))

    @tool(
        "agent_get_status",
        "Get the coding agent's current status for this project "
        "(stopped, running, paused, pausing, paused_graceful, crashed) and its run configuration.",
        EMPTY_SCHEMA,
    )
    async def agent_get_status(args: dict[str, Any]) -> dict[str, Any]:
        return await _run("get status of", lambda: agent_router.get_agent_status(project_name))

    @tool(
        "agent_start",
        "Start the coding agent for this project so it begins implementing pending features. "
        "Uses the global settings (model, YOLO mode, batch size) unless overridden.",
        AGENT_START_SCHEMA,
    )
    async def agent_start(args: dict[str, Any]) -> dict[str, Any]:
        try:
            request = AgentStartRequest(
                yolo_mode=args.get("yolo_mode"),
                max_concurrency=args.get("max_concurrency"),
            )
        except ValidationError as e:
            return _error(f"Invalid arguments: {e.errors()[0].get('msg', str(e))}")
        return await _run("start", lambda: agent_router.start_agent(project_name, request))

    @tool(
        "agent_stop",
        "Stop the coding agent for this project immediately. Work in progress on the current feature is interrupted.",
        EMPTY_SCHEMA,
    )
    async def agent_stop(args: dict[str, Any]) -> dict[str, Any]:
        return await _run("stop", lambda: agent_router.stop_agent(project_name))

    @tool(
        "agent_pause",
        "Gracefully pause the coding agent: it finishes the features it is currently working on, "
        "then pauses before picking up new work.",
        EMPTY_SCHEMA,
    )
    async def agent_pause(args: dict[str, Any]) -> dict[str, Any]:
        return await _run("pause", lambda: agent_router.graceful_pause_agent(project_name))

    @tool(
        "agent_resume",
        "Resume a paused coding agent for this project.",
        EMPTY_SCHEMA,
    )
    async def agent_resume(args: dict[str, Any]) -> dict[str, Any]:
        try:
            manager = agent_router.get_project_manager(project_name)
        except HTTPException as e:
            return _error(str(e.detail))
        # A hard pause (SIGSTOP) and a graceful pause (drain) resume differently
        if manager.status == "paused":
            return await _run("resume", lambda: agent_router.resume_agent(project_name))
        return await _run("resume", lambda: agent_router.graceful_resume_agent(project_name))

    return [agent_get_status, agent_start, agent_stop, agent_pause, agent_resume]


def create_agent_control_server(project_name: str) -> McpSdkServerConfig:
    """Create the in-process agent control MCP server for a project."""
    return create_sdk_mcp_server(
        name=AGENT_CONTROL_SERVER_NAME,
        version="1.0.0",
        tools=build_agent_control_tools(project_name),
    )
