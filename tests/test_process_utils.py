"""Tests for process_utils — process group kill."""
import os
import subprocess
import sys
import time

import pytest

from server.utils.process_utils import kill_process_tree


@pytest.mark.skipif(sys.platform == "win32", reason="Process groups differ on Windows")
class TestKillProcessGroup:
    def test_kills_children_via_process_group(self):
        proc = subprocess.Popen(
            ["bash", "-c", "sleep 300 & echo $!; wait"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        child_pid = int(proc.stdout.readline().decode().strip())
        assert _pid_alive(child_pid)
        result = kill_process_tree(proc, timeout=3.0)
        time.sleep(0.5)
        assert not _pid_alive(child_pid)
        assert result.status in ("success", "partial")

    def test_kills_deeply_nested_children(self):
        proc = subprocess.Popen(
            ["bash", "-c", "bash -c 'sleep 300' & echo $!; wait"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        grandchild_pid = int(proc.stdout.readline().decode().strip())
        assert _pid_alive(grandchild_pid)
        kill_process_tree(proc, timeout=3.0)
        time.sleep(0.5)
        assert not _pid_alive(grandchild_pid)

    def test_handles_already_dead_process(self):
        proc = subprocess.Popen(["true"], start_new_session=True)
        proc.wait()
        result = kill_process_tree(proc, timeout=1.0)
        assert result.status in ("success", "partial", "failure")


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
