"""
Orchestrator Completion Tests
=============================

Regression tests for #13: the orchestrator must not keep spawning regression
testing sessions once no coding work can make progress.

Run with: python -m pytest test_orchestrator_completion.py
"""

from unittest.mock import MagicMock

import pytest

import parallel_orchestrator
from parallel_orchestrator import MAX_FEATURE_RETRIES, ParallelOrchestrator


def _feature(fid: int, passes: bool = False, deps: list[int] | None = None, **extra) -> dict:
    return {
        "id": fid,
        "name": f"Feature {fid}",
        "priority": fid,
        "passes": passes,
        "in_progress": extra.get("in_progress", False),
        "needs_human_input": extra.get("needs_human_input", False),
        "dependencies": deps or [],
    }


@pytest.fixture
def orchestrator(tmp_path, monkeypatch):
    monkeypatch.setattr(parallel_orchestrator.debug_log, "log_file", tmp_path / "debug.log")
    orch = ParallelOrchestrator(tmp_path, testing_agent_ratio=1)
    yield orch
    orch.cleanup()


class TestStallState:
    def test_ready_feature_is_work(self, orchestrator):
        features = [_feature(1, passes=True), _feature(2, deps=[1])]
        assert orchestrator.get_stall_state(features) == "work"

    def test_resumable_feature_is_work(self, orchestrator):
        features = [_feature(1, passes=True), _feature(2, deps=[99], in_progress=True)]
        assert orchestrator.get_stall_state(features) == "work"

    def test_dependency_on_failed_feature_is_blocked(self, orchestrator):
        features = [_feature(1, passes=True), _feature(2), _feature(3, deps=[2])]
        orchestrator._failure_counts[2] = MAX_FEATURE_RETRIES
        assert orchestrator.get_stall_state(features) == "blocked"

    def test_dependency_cycle_is_blocked(self, orchestrator):
        features = [_feature(1, deps=[2]), _feature(2, deps=[1])]
        assert orchestrator.get_stall_state(features) == "blocked"

    def test_needs_human_input_waits(self, orchestrator):
        features = [_feature(1, passes=True), _feature(2, needs_human_input=True), _feature(3, deps=[2])]
        assert orchestrator.get_stall_state(features) == "human_input"

    def test_running_testing_agent_waits(self, orchestrator):
        features = [_feature(1, passes=True), _feature(2, deps=[3]), _feature(3, deps=[2])]
        orchestrator.running_testing_agents[1234] = (1, MagicMock())
        assert orchestrator.get_stall_state(features) == "testing"


class TestTestingAgentGating:
    def test_no_testing_agents_without_coding_agents(self, orchestrator, monkeypatch):
        spawn = MagicMock(return_value=(True, "ok"))
        monkeypatch.setattr(orchestrator, "_spawn_testing_agent", spawn)
        features = [_feature(1, passes=True), _feature(2, needs_human_input=True)]

        orchestrator._maintain_testing_agents(features)

        spawn.assert_not_called()

    def test_no_testing_agents_when_all_complete(self, orchestrator, monkeypatch):
        spawn = MagicMock(return_value=(True, "ok"))
        monkeypatch.setattr(orchestrator, "_spawn_testing_agent", spawn)
        orchestrator.running_coding_agents[2] = MagicMock()
        features = [_feature(1, passes=True), _feature(2, passes=True)]

        orchestrator._maintain_testing_agents(features)

        spawn.assert_not_called()

    def test_testing_agents_run_alongside_coding_agents(self, orchestrator, monkeypatch):
        def fake_spawn():
            orchestrator.running_testing_agents[4321] = (1, MagicMock())
            return True, "ok"

        spawn = MagicMock(side_effect=fake_spawn)
        monkeypatch.setattr(orchestrator, "_spawn_testing_agent", spawn)
        orchestrator.running_coding_agents[2] = MagicMock()
        features = [_feature(1, passes=True), _feature(2, in_progress=True)]

        orchestrator._maintain_testing_agents(features)

        spawn.assert_called_once()
