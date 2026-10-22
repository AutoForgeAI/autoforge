"""
Subprocess Encoding Tests
=========================

Regression tests for issue #138: on Windows, agent subprocess output was
decoded with the ANSI code page (CP1252), crashing the orchestrator's output
reader thread with UnicodeDecodeError on non-ASCII output.

Two halves must agree on UTF-8:
- the child must *write* UTF-8 to the pipe (PYTHONIOENCODING=utf-8)
- the parent must *read* UTF-8 from the pipe (encoding="utf-8", errors="replace")

Run with: python -m pytest test_subprocess_encoding.py -v
"""

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import parallel_orchestrator
from parallel_orchestrator import ParallelOrchestrator

NON_ASCII = "done ✓ — café 🚀 日本語"


@pytest.fixture
def orchestrator(tmp_path: Path) -> ParallelOrchestrator:
    return ParallelOrchestrator(project_dir=tmp_path, max_concurrency=1)


def _capture_popen_kwargs(spawn) -> dict:
    """Run a spawn function with Popen/Thread mocked and return Popen's kwargs."""
    with patch.object(parallel_orchestrator.subprocess, "Popen", return_value=MagicMock()) as popen, \
            patch.object(parallel_orchestrator.threading, "Thread"):
        ok, _ = spawn()
    assert ok
    popen.assert_called_once()
    return dict(popen.call_args.kwargs)


def _assert_utf8_pipe(kwargs: dict) -> None:
    assert kwargs["encoding"] == "utf-8"
    assert kwargs["errors"] == "replace"
    assert kwargs["env"]["PYTHONIOENCODING"] == "utf-8"


def test_coding_agent_uses_utf8_pipe(orchestrator: ParallelOrchestrator) -> None:
    _assert_utf8_pipe(_capture_popen_kwargs(lambda: orchestrator._spawn_coding_agent(1)))


def test_coding_agent_batch_uses_utf8_pipe(orchestrator: ParallelOrchestrator) -> None:
    _assert_utf8_pipe(_capture_popen_kwargs(lambda: orchestrator._spawn_coding_agent_batch([1, 2])))


def test_testing_agent_uses_utf8_pipe(orchestrator: ParallelOrchestrator) -> None:
    with patch.object(orchestrator, "_get_test_batch", return_value=[1]):
        _assert_utf8_pipe(_capture_popen_kwargs(orchestrator._spawn_testing_agent))


def test_child_env_overrides_legacy_parent_encoding(orchestrator: ParallelOrchestrator) -> None:
    """Even if the parent environment forces CP1252, children get UTF-8."""
    with patch.dict(os.environ, {"PYTHONIOENCODING": "cp1252"}):
        kwargs = _capture_popen_kwargs(lambda: orchestrator._spawn_coding_agent(1))
    assert kwargs["env"]["PYTHONIOENCODING"] == "utf-8"


def test_non_ascii_child_output_round_trips() -> None:
    """End to end: a Python child on a CP1252-like setup prints non-ASCII text
    that the parent reads back intact, as the orchestrator does."""
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}  # simulate the Windows default
    env.update({"PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"})  # orchestrator overrides
    proc = subprocess.Popen(
        [sys.executable, "-c", f"print({NON_ASCII!r})"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert proc.stdout is not None
    lines = [line.rstrip("\n") for line in proc.stdout]
    assert proc.wait() == 0
    assert lines == [NON_ASCII]


def test_reader_survives_invalid_utf8_bytes() -> None:
    """Bytes that are invalid UTF-8 (like 0x8f from the issue) must not raise."""
    proc = subprocess.Popen(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'ok \\x8f\\xff end\\n')"],
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert proc.stdout is not None
    lines = list(proc.stdout)
    assert proc.wait() == 0
    assert lines == ["ok �� end\n"]
