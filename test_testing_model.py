"""
Unit tests for per-agent-type model selection in the parallel orchestrator.

Coding agents use ``model``; regression testing agents use ``testing_model``
and fall back to ``model`` when no override is configured.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from parallel_orchestrator import ParallelOrchestrator


def _spawned_model(spawn) -> str | None:
    """Run a spawn method with Popen stubbed out and return the --model it passed."""
    captured: list[list[str]] = []

    def fake_popen(cmd, **kwargs):
        captured.append(cmd)
        raise OSError("not spawning in tests")

    with patch("parallel_orchestrator.subprocess.Popen", side_effect=fake_popen):
        spawn()

    assert captured, "spawn method never reached Popen"
    cmd = captured[0]
    if "--model" not in cmd:
        return None
    return cmd[cmd.index("--model") + 1]


class TestTestingModel(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _orchestrator(self, **kwargs) -> ParallelOrchestrator:
        orch = ParallelOrchestrator(project_dir=self.project_dir, **kwargs)
        self.addCleanup(orch._engine.dispose)
        return orch

    def _testing_model(self, orch: ParallelOrchestrator) -> str | None:
        with patch.object(orch, "_get_test_batch", return_value=[1, 2]):
            return _spawned_model(orch._spawn_testing_agent)

    def test_testing_agent_uses_testing_model(self):
        orch = self._orchestrator(model="claude-opus-4-7", testing_model="claude-sonnet-4-6")
        assert self._testing_model(orch) == "claude-sonnet-4-6"

    def test_coding_agent_keeps_coding_model(self):
        orch = self._orchestrator(model="claude-opus-4-7", testing_model="claude-sonnet-4-6")
        assert _spawned_model(lambda: orch._spawn_coding_agent(1)) == "claude-opus-4-7"
        assert _spawned_model(lambda: orch._spawn_coding_agent_batch([1, 2])) == "claude-opus-4-7"

    def test_testing_model_falls_back_to_model(self):
        orch = self._orchestrator(model="claude-opus-4-7")
        assert self._testing_model(orch) == "claude-opus-4-7"

        orch = self._orchestrator(model="claude-opus-4-7", testing_model="")
        assert self._testing_model(orch) == "claude-opus-4-7"

    def test_no_model_passes_no_flag(self):
        orch = self._orchestrator()
        assert self._testing_model(orch) is None


if __name__ == "__main__":
    unittest.main()
