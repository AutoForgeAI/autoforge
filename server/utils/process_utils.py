"""
Process Utilities
=================

Shared utilities for process management across the codebase.
"""

import logging
import subprocess
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

    On Windows, subprocess.terminate() only kills the immediate process, leaving
    orphaned child processes (e.g., spawned browser instances, coding/testing agents).
    This function uses psutil to kill the entire process tree.

    Args:
        proc: The subprocess.Popen object to kill
        timeout: Seconds to wait for graceful termination before force-killing

    Returns:
        KillResult with status and statistics about the termination
    """
    result = KillResult(status="success", parent_pid=proc.pid)

    try:
        parent = psutil.Process(proc.pid)
        # Get all children recursively before terminating
        children = parent.children(recursive=True)
        result.children_found = len(children)

        logger.debug(
            "Killing process tree: PID %d with %d children",
            proc.pid, len(children)
        )

        # Terminate children first (graceful)
        for child in children:
            try:
                logger.debug("Terminating child PID %d (%s)", child.pid, child.name())
                child.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                # NoSuchProcess: already dead
                # AccessDenied: Windows can raise this for system processes or already-exited processes
                logger.debug("Child PID %d already gone or inaccessible: %s", child.pid, e)

        # Wait for children to terminate
        gone, still_alive = psutil.wait_procs(children, timeout=timeout)
        result.children_terminated = len(gone)

        logger.debug(
            "Children after graceful wait: %d terminated, %d still alive",
            len(gone), len(still_alive)
        )

        # Force kill any remaining children
        for child in still_alive:
            try:
                logger.debug("Force-killing child PID %d", child.pid)
                child.kill()
                result.children_killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.debug("Child PID %d gone during force-kill: %s", child.pid, e)

        if result.children_killed > 0:
            result.status = "partial"

        # Now terminate the parent
        logger.debug("Terminating parent PID %d", proc.pid)
        proc.terminate()
        try:
            proc.wait(timeout=timeout)
            logger.debug("Parent PID %d terminated gracefully", proc.pid)
        except subprocess.TimeoutExpired:
            logger.debug("Parent PID %d did not terminate, force-killing", proc.pid)
            proc.kill()
            proc.wait()
            result.parent_forcekilled = True
            result.status = "partial"

        logger.debug(
            "Process tree kill complete: status=%s, children=%d (terminated=%d, killed=%d)",
            result.status, result.children_found,
            result.children_terminated, result.children_killed
        )

    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        # NoSuchProcess: Process already dead
        # AccessDenied: Windows can raise this for protected/system processes
        # In either case, just ensure cleanup
        logger.debug("Parent PID %d inaccessible (%s), attempting direct cleanup", proc.pid, e)
        try:
            proc.terminate()
            proc.wait(timeout=1)
            logger.debug("Direct termination of PID %d succeeded", proc.pid)
        except (subprocess.TimeoutExpired, OSError):
            try:
                proc.kill()
                logger.debug("Direct force-kill of PID %d succeeded", proc.pid)
            except OSError as kill_error:
                logger.debug("Direct force-kill of PID %d failed: %s", proc.pid, kill_error)
                result.status = "failure"

    return result
