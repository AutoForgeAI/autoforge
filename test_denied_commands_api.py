"""
Tests for the denied-commands REST endpoints in server/routers/projects.py.
"""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from autoforge_paths import get_denied_commands_path
from security import bash_security_hook
from server.routers import projects


class TestDeniedCommandsEndpoints(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_dir = Path(self._tmp.name)
        app = FastAPI()
        app.include_router(projects.router)
        self.client = TestClient(app)

        registry_funcs = list(projects._get_registry_functions())
        registry_funcs[2] = lambda name: self.project_dir if name == "demo" else None
        self._patch = patch.object(projects, "_get_registry_functions", return_value=tuple(registry_funcs))
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def _deny(self, cmd: str) -> None:
        input_data = {"tool_name": "Bash", "tool_input": {"command": cmd}}
        asyncio.run(bash_security_hook(input_data, context={"project_dir": str(self.project_dir)}))

    def test_empty_when_no_log(self):
        resp = self.client.get("/api/projects/demo/denied-commands")
        assert resp.status_code == 200
        assert resp.json() == {"commands": [], "total": 0}

    def test_lists_grouped_denials(self):
        self._deny("pytest -q")
        self._deny("pytest tests/")
        self._deny("openssl rand -hex 8")

        resp = self.client.get("/api/projects/demo/denied-commands")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert [c["command"] for c in data["commands"]] == ["pytest", "openssl"]
        assert data["commands"][0]["count"] == 2
        assert data["commands"][0]["kind"] == "not_allowed"
        assert data["commands"][0]["last_full_command"] == "pytest tests/"

    def test_clear(self):
        self._deny("pytest")
        assert get_denied_commands_path(self.project_dir).exists()

        resp = self.client.delete("/api/projects/demo/denied-commands")
        assert resp.status_code == 200
        assert not get_denied_commands_path(self.project_dir).exists()
        assert self.client.get("/api/projects/demo/denied-commands").json()["total"] == 0

    def test_unknown_project_404(self):
        assert self.client.get("/api/projects/missing/denied-commands").status_code == 404

    def test_invalid_name_400(self):
        assert self.client.get("/api/projects/bad.name/denied-commands").status_code == 400


if __name__ == "__main__":
    unittest.main()
