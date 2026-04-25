"""
Process Utilities
=================

Shared utilities for process management across the codebase.
"""

import logging
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Literal

import psutil

logger = logging.getLogger(__name__)


@dataclass
class KillResult:
    """Result of a process tree kill operation.

    Attributes:
        status: "success" if all processes terminated, "partial" if some required
            force-kill, "failure" if parent couldn't be killed
        parent_pid: PID of the parent process
        children_found: Number of child processes found
        children_terminated: Number of children that terminated gracefully
        children_killed: Number of children that required SIGKILL
        parent_forcekilled: Whether the parent required SIGKILL
    """

    status: Literal["success", "partial", "failure"]
    parent_pid: int
    children_found: int = 0
    children_terminated: int = 0
    children_killed: int = 0
    parent_forcekilled: bool = False


def kill_process_tree(proc: subprocess.Popen, timeout: float = 5.0) -> KillResult:
    """Kill a process and all its child processes.

    Uses a two-phase approach for reliable cleanup:
    1. If the process is a process group leader (start_new_session=True on Unix),
       kill the entire group via os.killpg(). This is atomic and immune to the
       TOCTOU race where children get reparented to PID 1.
    2. Fall back to psutil tree walk for Windows and any stragglers.

    Args:
        proc: The subprocess.Popen object to kill
        timeout: Seconds to wait for graceful termination before force-killing

    Returns:
        KillResult with status and statistics about the termination
    """
    result = KillResult(status="success", parent_pid=proc.pid)

    # Phase 1: Process group kill (Unix only, atomic, no TOCTOU race)
    if sys.platform != "win32":
        try:
            pgid = os.getpgid(proc.pid)
            if pgid == proc.pid:
                logger.debug("Killing process group PGID %d", pgid)
                try:
                    os.killpg(pgid, signal.SIGTERM)
                except ProcessLookupError:
                    pass

                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline:
                    try:
                        os.killpg(pgid, 0)
                    except ProcessLookupError:
                        break
                    time.sleep(0.1)
                else:
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                        result.status = "partial"
                    except ProcessLookupError:
                        pass
        except (ProcessLookupError, OSError) as e:
            logger.debug("Process group kill skipped for PID %d: %s", proc.pid, e)

    # Phase 2: psutil tree walk (catches Windows + non-group-leader children)
    try:
        parent = psutil.Process(proc.pid)
        children = parent.children(recursive=True)
        result.children_found = len(children)

        for child in children:
            try:
                child.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        gone, still_alive = psutil.wait_procs(children, timeout=timeout)
        result.children_terminated = len(gone)

        for child in still_alive:
            try:
                child.kill()
                result.children_killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if result.children_killed > 0:
            result.status = "partial"

        proc.terminate()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            result.parent_forcekilled = True
            result.status = "partial"

    except (psutil.NoSuchProcess, psutil.AccessDenied):
        try:
            proc.terminate()
            proc.wait(timeout=1)
        except (subprocess.TimeoutExpired, OSError):
            try:
                proc.kill()
            except OSError:
                result.status = "failure"

    return result
