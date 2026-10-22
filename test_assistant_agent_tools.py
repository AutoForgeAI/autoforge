"""
Unit tests for the assistant's agent control MCP tools.

Exercises server/services/assistant_agent_tools.py against a fake process
manager so no real agent subprocess is spawned.
"""

import asyncio
import json
import unittest
from datetime import datetime
from unittest.mock import patch

from fastapi import HTTPException

from server.services.assistant_agent_tools import (
    AGENT_CONTROL_SERVER_NAME,
    AGENT_CONTROL_TOOLS,
    build_agent_control_tools,
    create_agent_control_server,
)
from server.services.assistant_chat_session import (
    ASSISTANT_MCP_TOOLS,
    DISALLOWED_ASSISTANT_TOOLS,
)


class FakeManager:
    """Minimal stand-in for AgentProcessManager."""

    def __init__(self, status: str = "stopped"):
        self.status = status
        self.pid = None
        self.started_at = None
        self.yolo_mode = False
        self.model = "claude-opus-4-6"
        self.parallel_mode = False
        self.max_concurrency = None
        self.testing_agent_ratio = 1
        self.calls: list[tuple[str, dict]] = []

    async def healthcheck(self) -> bool:
        return True

    async def start(self, **kwargs):
        self.calls.append(("start", kwargs))
        if self.status != "stopped":
            return False, "Agent is already running"
        self.status = "running"
        return True, "Agent started"

    async def stop(self):
        self.calls.append(("stop", {}))
        self.status = "stopped"
        return True, "Agent stopped"

    async def pause(self):
        self.calls.append(("pause", {}))
        self.status = "paused"
        return True, "Agent paused"

    async def resume(self):
        self.calls.append(("resume", {}))
        self.status = "running"
        return True, "Agent resumed"

    async def graceful_pause(self):
        self.calls.append(("graceful_pause", {}))
        self.status = "pausing"
        return True, "Pausing"

    async def graceful_resume(self):
        self.calls.append(("graceful_resume", {}))
        self.status = "running"
        return True, "Resumed"


def _payload(result: dict) -> dict:
    payload: dict = json.loads(result["content"][0]["text"])
    return payload


class TestAgentControlTools(unittest.TestCase):
    def setUp(self):
        self.manager = FakeManager()
        self.patches = [
            patch("server.routers.agent.get_project_manager", return_value=self.manager),
            patch(
                "server.routers.agent._get_settings_defaults",
                return_value=(False, "claude-opus-4-6", 1, 3, 3),
            ),
            # Skip scheduler notifications (no registered project in tests)
            patch("server.routers.agent._get_project_path", return_value=None),
        ]
        for p in self.patches:
            p.start()
        self.tools = {t.name: t for t in build_agent_control_tools("demo")}

    def tearDown(self):
        for p in self.patches:
            p.stop()

    def call(self, name: str, args: dict | None = None) -> dict:
        return asyncio.run(self.tools[name].handler(args or {}))

    def test_tool_names_match_exported_list(self):
        expected = {f"mcp__{AGENT_CONTROL_SERVER_NAME}__{name}" for name in self.tools}
        self.assertEqual(expected, set(AGENT_CONTROL_TOOLS))

    def test_assistant_allows_agent_control_tools(self):
        for name in AGENT_CONTROL_TOOLS:
            self.assertIn(name, ASSISTANT_MCP_TOOLS)
            self.assertNotIn(name, DISALLOWED_ASSISTANT_TOOLS)

    def test_server_config_is_in_process(self):
        config = create_agent_control_server("demo")
        self.assertEqual(config["type"], "sdk")
        self.assertEqual(config["name"], AGENT_CONTROL_SERVER_NAME)

    def test_get_status(self):
        result = self.call("agent_get_status")
        self.assertNotIn("is_error", result)
        self.assertEqual(_payload(result)["status"], "stopped")

    def test_get_status_while_running_is_json_serializable(self):
        started_at = datetime.now()
        self.manager.status = "running"
        self.manager.pid = 1234
        self.manager.started_at = started_at
        result = self.call("agent_get_status")
        self.assertNotIn("is_error", result)
        payload = _payload(result)
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["started_at"], started_at.isoformat())

    def test_start_uses_settings_defaults_and_overrides(self):
        result = self.call("agent_start", {"max_concurrency": 3})
        payload = _payload(result)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["status"], "running")
        action, kwargs = self.manager.calls[-1]
        self.assertEqual(action, "start")
        self.assertEqual(kwargs["max_concurrency"], 3)
        self.assertFalse(kwargs["yolo_mode"])
        self.assertEqual(kwargs["model"], "claude-opus-4-6")

    def test_start_rejects_invalid_concurrency(self):
        result = self.call("agent_start", {"max_concurrency": 9})
        self.assertTrue(result.get("is_error"))
        self.assertEqual(self.manager.calls, [])

    def test_failed_action_is_reported_as_error(self):
        self.manager.status = "running"
        result = self.call("agent_start")
        self.assertTrue(result.get("is_error"))
        self.assertFalse(_payload(result)["success"])

    def test_stop(self):
        self.manager.status = "running"
        payload = _payload(self.call("agent_stop"))
        self.assertTrue(payload["success"])
        self.assertEqual(payload["status"], "stopped")

    def test_pause_is_graceful(self):
        self.manager.status = "running"
        self.call("agent_pause")
        self.assertEqual(self.manager.calls[-1][0], "graceful_pause")

    def test_resume_after_hard_pause(self):
        self.manager.status = "paused"
        self.call("agent_resume")
        self.assertEqual(self.manager.calls[-1][0], "resume")

    def test_resume_after_graceful_pause(self):
        self.manager.status = "paused_graceful"
        self.call("agent_resume")
        self.assertEqual(self.manager.calls[-1][0], "graceful_resume")

    def test_unknown_project_returns_error(self):
        with patch(
            "server.routers.agent.get_project_manager",
            side_effect=HTTPException(status_code=404, detail="Project 'demo' not found in registry"),
        ):
            for name in self.tools:
                result = self.call(name)
                self.assertTrue(result.get("is_error"), name)
                self.assertIn("not found", _payload(result)["error"])


if __name__ == "__main__":
    unittest.main()
