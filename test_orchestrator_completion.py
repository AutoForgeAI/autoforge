"""
Orchestrator Completion Tests
=============================

Tests that the orchestrator stops working (and stops spawning regression
testing agents) once no more coding progress is possible.

Run with: python -m pytest test_orchestrator_completion.py -v
"""

import asyncio
from pathlib import Path

import pytest

from api.database import Feature
from parallel_orchestrator import MAX_FEATURE_RETRIES, ParallelOrchestrator


def _make_orchestrator(project_dir: Path, features: list[dict]) -> ParallelOrchestrator:
    orchestrator = ParallelOrchestrator(project_dir, max_concurrency=1, testing_agent_ratio=1)
    session = orchestrator.get_session()
    try:
        for i, overrides in enumerate(features, start=1):
            data = {
                "id": i,
                "priority": i,
                "category": "test",
                "name": f"Feature {i}",
                "description": "desc",
                "steps": [],
            }
            data.update(overrides)
            session.add(Feature(**data))
        session.commit()
    finally:
        session.close()
    return orchestrator


@pytest.fixture
def spawns(monkeypatch):
    """Record agent spawns instead of starting real subprocesses."""
    calls: dict[str, list] = {"testing": [], "coding": []}

    def fake_testing(self):
        calls["testing"].append(True)
        return False, "test stub"

    def fake_batch(self, feature_ids):
        calls["coding"].append(feature_ids)
        return False, "test stub"

    def fake_start(self, feature_id, resume=False):
        calls["coding"].append([feature_id])
        return False, "test stub"

    monkeypatch.setattr(ParallelOrchestrator, "_spawn_testing_agent", fake_testing)
    monkeypatch.setattr(ParallelOrchestrator, "start_feature_batch", fake_batch)
    monkeypatch.setattr(ParallelOrchestrator, "start_feature", fake_start)
    return calls


def _run_loop(orchestrator: ParallelOrchestrator, timeout: float = 10.0) -> None:
    asyncio.run(asyncio.wait_for(orchestrator.run_loop(), timeout=timeout))


class TestHasCodingWork:
    def test_ready_feature_is_work(self, tmp_path):
        orch = _make_orchestrator(tmp_path, [{"passes": True}, {}])
        assert orch.has_coding_work() is True

    def test_human_input_only_is_not_work(self, tmp_path):
        orch = _make_orchestrator(tmp_path, [{"passes": True}, {"needs_human_input": True}])
        assert orch.has_coding_work() is False

    def test_missing_dependency_is_not_work(self, tmp_path):
        orch = _make_orchestrator(tmp_path, [{"passes": True}, {"dependencies": [99]}])
        assert orch.has_coding_work() is False

    def test_dependency_on_failed_feature_is_not_work(self, tmp_path):
        orch = _make_orchestrator(tmp_path, [{"passes": True}, {}, {"dependencies": [2]}])
        orch._failure_counts[2] = MAX_FEATURE_RETRIES
        assert orch.has_coding_work() is False


class TestTestingAgentSpawning:
    def test_spawns_while_coding_work_exists(self, tmp_path, spawns):
        orch = _make_orchestrator(tmp_path, [{"passes": True}, {}])
        orch._maintain_testing_agents()
        assert len(spawns["testing"]) == 1

    def test_no_spawn_when_stalled_on_human_input(self, tmp_path, spawns):
        orch = _make_orchestrator(tmp_path, [{"passes": True}, {"needs_human_input": True}])
        orch._maintain_testing_agents()
        assert spawns["testing"] == []

    def test_no_spawn_when_all_complete(self, tmp_path, spawns):
        orch = _make_orchestrator(tmp_path, [{"passes": True}, {"passes": True}])
        orch._maintain_testing_agents()
        assert spawns["testing"] == []


class TestRunLoopStops:
    def test_exits_when_all_features_pass(self, tmp_path, spawns, capsys):
        orch = _make_orchestrator(tmp_path, [{"passes": True}, {"passes": True}])
        _run_loop(orch)
        assert "All features complete!" in capsys.readouterr().out
        assert spawns == {"testing": [], "coding": []}

    def test_exits_when_remaining_features_are_unreachable(self, tmp_path, spawns, capsys):
        orch = _make_orchestrator(tmp_path, [{"passes": True}, {"dependencies": [99]}])
        _run_loop(orch)
        out = capsys.readouterr().out
        assert "No more work possible" in out
        assert "Blocked by unmet dependencies: #2" in out
        assert spawns == {"testing": [], "coding": []}

    def test_waits_without_testing_while_awaiting_human_input(self, tmp_path, spawns, capsys):
        orch = _make_orchestrator(tmp_path, [{"passes": True}, {"needs_human_input": True}])
        with pytest.raises((asyncio.TimeoutError, TimeoutError)):
            _run_loop(orch, timeout=1.5)
        out = capsys.readouterr().out
        assert out.count("Waiting for human input on feature(s) #2") == 1
        assert spawns == {"testing": [], "coding": []}
