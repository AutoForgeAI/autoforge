"""
Tests for server/utils/process_utils.py

Covers the fallback for psutil's pidfd_open() EINVAL race on Linux 6.x (#167).
"""

import errno
import subprocess
import sys
import time
from unittest.mock import patch

import psutil
import pytest

from server.utils.process_utils import kill_process_tree, wait_procs_safe

EINVAL_ERROR = OSError(errno.EINVAL, "Invalid argument")


def _spawn_sleeper() -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])


def test_wait_procs_safe_falls_back_on_einval():
    proc = _spawn_sleeper()
    try:
        ps = psutil.Process(proc.pid)
        proc.terminate()
        with patch("psutil.wait_procs", side_effect=EINVAL_ERROR):
            gone, alive = wait_procs_safe([ps], timeout=5)
        assert gone == [ps]
        assert alive == []
    finally:
        proc.kill()
        proc.wait()


def test_wait_procs_safe_reports_still_alive_after_timeout():
    proc = _spawn_sleeper()
    try:
        ps = psutil.Process(proc.pid)
        with patch("psutil.wait_procs", side_effect=EINVAL_ERROR):
            gone, alive = wait_procs_safe([ps], timeout=0.3)
        assert gone == []
        assert alive == [ps]
    finally:
        proc.kill()
        proc.wait()


def test_wait_procs_safe_reraises_other_oserrors():
    with patch("psutil.wait_procs", side_effect=OSError(errno.EPERM, "nope")):
        with pytest.raises(OSError):
            wait_procs_safe([], timeout=0.1)


def test_kill_process_tree_survives_einval():
    parent = subprocess.Popen([
        sys.executable, "-c",
        "import subprocess, sys, time;"
        "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']);"
        "time.sleep(30)",
    ])
    try:
        # Wait for the grandchild to appear
        ps_parent = psutil.Process(parent.pid)
        for _ in range(50):
            if ps_parent.children(recursive=True):
                break
            time.sleep(0.1)
        children = ps_parent.children(recursive=True)
        assert children

        with patch("psutil.wait_procs", side_effect=EINVAL_ERROR):
            result = kill_process_tree(parent, timeout=5)

        assert result.status in ("success", "partial")
        assert result.children_found == len(children)
        assert parent.poll() is not None
        for child in children:
            assert not child.is_running() or child.status() == psutil.STATUS_ZOMBIE
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait()
