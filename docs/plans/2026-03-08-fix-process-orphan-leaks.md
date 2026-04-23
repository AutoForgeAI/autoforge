# Fix Process Orphan Leaks — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate orphaned Chrome/node/esbuild processes that accumulate and cause OOM kills (issues #164, #197).

**Architecture:** Defense-in-depth across 3 layers: (1) Process groups via `start_new_session=True` so entire subtrees can be killed atomically with `os.killpg()`, eliminating the TOCTOU race in the current `psutil.children()` approach. (2) Fix `cli.js` to kill the process group instead of a single PID. (3) Add a periodic orphan reaper in the server that sweeps for reparented processes under PID 1.

**Tech Stack:** Python 3.11+ (psutil, subprocess), Node.js (child_process), Linux process groups

---

## Context for the Implementer

### The Bug

When a Claude subagent exits, `kill_process_tree()` uses `psutil.Process(pid).children(recursive=True)` to find children. But between the Claude process dying and the tree walk, children get **reparented to PID 1**. They're no longer in the tree, so they survive. Each leaked Chrome instance is ~200MB; over hours this hits the 10Gi memory limit.

### Files Overview

| File | Role |
|------|------|
| `server/utils/process_utils.py` | `kill_process_tree()` — the core kill function |
| `server/services/process_manager.py` | `AgentProcessManager` — manages agent subprocess lifecycle |
| `server/services/dev_server_manager.py` | `DevServerProcessManager` — manages dev server subprocess |
| `parallel_orchestrator.py` | Orchestrator — spawns coding/testing agent subprocesses |
| `lib/cli.js` | Node.js PID 1 entry point — spawns uvicorn |

### Key Constraint

- `start_new_session=True` is Linux/macOS only. On Windows, use `CREATE_NEW_PROCESS_GROUP` flag instead.
- Must not break Windows support (the codebase has extensive Windows handling).

---

### Task 1: Add process-group-aware kill to `process_utils.py`

**Files:**
- Modify: `server/utils/process_utils.py`
- Create: `tests/test_process_utils.py`

**Step 1: Write the failing test**

Create `tests/test_process_utils.py`:

```python
"""Tests for process_utils — process group kill."""
import os
import signal
import subprocess
import sys
import time

import pytest

from server.utils.process_utils import kill_process_tree


@pytest.mark.skipif(sys.platform == "win32", reason="Process groups differ on Windows")
class TestKillProcessGroup:
    def test_kills_children_via_process_group(self):
        """Children in the same process group are killed even if reparented."""
        # Spawn a shell that starts a background sleep (simulates orphan-to-be)
        proc = subprocess.Popen(
            ["bash", "-c", "sleep 300 & echo $!; wait"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        # Read the child PID
        child_pid_line = proc.stdout.readline().decode().strip()
        child_pid = int(child_pid_line)

        # Verify child is alive
        assert _pid_alive(child_pid), "child should be alive before kill"

        result = kill_process_tree(proc, timeout=3.0)
        time.sleep(0.5)

        assert not _pid_alive(child_pid), "child should be dead after process group kill"
        assert result.status in ("success", "partial")

    def test_kills_deeply_nested_children(self):
        """Grandchildren in the same process group are also killed."""
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
        """Killing an already-exited process doesn't raise."""
        proc = subprocess.Popen(
            ["true"],
            start_new_session=True,
        )
        proc.wait()
        result = kill_process_tree(proc, timeout=1.0)
        # Should not raise, status can be success or failure
        assert result.status in ("success", "partial", "failure")


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/vandang/GitProjects/autoforge-fork && python -m pytest tests/test_process_utils.py -v`
Expected: FAIL — `start_new_session` children survive because `kill_process_tree` doesn't use `os.killpg()`

**Step 3: Implement process-group kill in `kill_process_tree()`**

Replace the body of `kill_process_tree()` in `server/utils/process_utils.py` (lines 40-134).

Add these imports to the top of the file: `import os`, `import signal`, `import time`.

The new `kill_process_tree()` function uses a two-phase approach:
1. **Phase 1 (process group):** If on Unix and the process is a group leader (`os.getpgid(pid) == pid`), call `os.killpg(pgid, SIGTERM)`, wait up to `timeout`, then `os.killpg(pgid, SIGKILL)`. This atomically kills all processes in the group regardless of reparenting.
2. **Phase 2 (psutil fallback):** Walk the process tree via `psutil.Process(pid).children(recursive=True)` and terminate/kill remaining children. This handles Windows and processes not in the group.

See the full implementation in the function body below:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/vandang/GitProjects/autoforge-fork && python -m pytest tests/test_process_utils.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add server/utils/process_utils.py tests/test_process_utils.py
git commit -m "fix: add process-group kill to eliminate orphan TOCTOU race

Addresses #164, #197. kill_process_tree() now uses os.killpg() when the
subprocess was started with start_new_session=True, killing the entire
process group atomically before falling back to psutil tree walk."
```

---

### Task 2: Spawn all subprocesses with `start_new_session=True`

**Files:**
- Modify: `parallel_orchestrator.py` (4 spawn sites)
- Modify: `server/services/process_manager.py:464-474`
- Modify: `server/services/dev_server_manager.py` (both branches of start())

**Step 1: Add `start_new_session=True` to every `subprocess.Popen` call**

In each of the files above, add to the `popen_kwargs` dict, right after the existing Windows `creationflags` block:

```python
# On Unix: create new process group so kill_process_tree can use os.killpg()
if sys.platform != "win32":
    popen_kwargs["start_new_session"] = True
```

There are **6 spawn sites** total. For each, find the pattern:
```python
if sys.platform == "win32":
    popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
```
And add the Unix branch immediately after.

The 6 locations:
1. `parallel_orchestrator.py` `_spawn_coding_agent` (~line 862)
2. `parallel_orchestrator.py` `_spawn_coding_agent_batch` (~line 925)
3. `parallel_orchestrator.py` `_spawn_testing_agent_batch` (~line 1030)
4. `parallel_orchestrator.py` `run_initializer` (~line 1091)
5. `server/services/process_manager.py` `AgentProcessManager.start` (~line 472)
6. `server/services/dev_server_manager.py` `DevServerProcessManager.start` (both the Windows and Unix Popen calls)

**Step 2: Verify no tests break**

Run: `cd /Users/vandang/GitProjects/autoforge-fork && python -m pytest tests/ -v`
Expected: PASS

**Step 3: Commit**

```bash
git add parallel_orchestrator.py server/services/process_manager.py server/services/dev_server_manager.py
git commit -m "fix: spawn all subprocesses with start_new_session=True

Each subprocess now runs in its own process group, enabling atomic cleanup
via os.killpg(). This prevents children from escaping kill_process_tree()
by getting reparented to PID 1 before the psutil tree walk runs."
```

---

### Task 3: Fix `cli.js` to kill the process group on shutdown

**Files:**
- Modify: `lib/cli.js:507-518` (killProcess function)
- Modify: `lib/cli.js:715-728` (uvicorn spawn)

**Step 1: Update `killProcess()` to kill the process group**

Replace `killProcess` (lines 507-518) to send signal to negative PID (= process group):

```javascript
/** Kill a process and its children. Windows: taskkill /t. Unix: kill process group. */
function killProcess(pid) {
  try {
    if (IS_WIN) {
      execFileSync('taskkill', ['/pid', String(pid), '/t', '/f'], { stdio: 'ignore' });
    } else {
      // Kill entire process group (negative PID = PGID)
      try { process.kill(-pid, 'SIGTERM'); } catch { /* already dead */ }
      // Give a moment for graceful shutdown, then force
      try {
        execFileSync('kill', ['-0', String(-pid)], { stdio: 'ignore', timeout: 5000 });
        // Still alive, force kill
        try { process.kill(-pid, 'SIGKILL'); } catch { /* already dead */ }
      } catch {
        // Group already gone
      }
    }
  } catch {
    // Process/group may already be gone
  }
}
```

Note: Uses `execFileSync` instead of `execSync` to avoid shell injection (per project conventions).

**Step 2: Spawn uvicorn with `detached: true` to create process group**

Update the spawn call (~line 715):

```javascript
  const child = spawn(
    pyExe,
    [
      '-m', 'uvicorn',
      'server.main:app',
      '--host', host,
      '--port', String(port),
    ],
    {
      cwd: PKG_DIR,
      env: serverEnv,
      stdio: 'inherit',
      detached: !IS_WIN,  // Create new process group on Unix (setsid)
    }
  );
```

**Step 3: Commit**

```bash
git add lib/cli.js
git commit -m "fix: cli.js kills entire process group on shutdown

killProcess() now sends SIGTERM to -pid (the process group), ensuring
all child processes (uvicorn, agents, Chrome, dev servers) are terminated
on Ctrl+C or SIGTERM. Uses execFileSync instead of execSync for safety."
```

---

### Task 4: Add periodic orphan reaper to the server

**Files:**
- Create: `server/services/orphan_reaper.py`
- Modify: `server/main.py` (register reaper on startup/shutdown)

**Step 1: Create `server/services/orphan_reaper.py`**

This module runs a background asyncio task every 60s that:
1. Iterates all processes via `psutil.process_iter()`
2. Finds any with `ppid == 1` and name in `{chrome, chrome_crashpad, node, esbuild, npm, sh, bash}`
3. Skips processes younger than 30 seconds (grace period)
4. Terminates them (SIGTERM, then SIGKILL after 3s)
5. Only active on Linux (no-op on macOS/Windows)

See full implementation in the code block above (Task 4 in the first version of this plan).

**Step 2: Register in `server/main.py`**

Find the startup event handler and add:
```python
from server.services.orphan_reaper import start_reaper, stop_reaper
```

In startup: `start_reaper()`
In shutdown: `stop_reaper()`

**Step 3: Commit**

```bash
git add server/services/orphan_reaper.py server/main.py
git commit -m "fix: add periodic orphan reaper as safety net

Scans every 60s for chrome/node/esbuild processes orphaned under PID 1
and kills them after a 30s grace period. Only active on Linux containers."
```

---

### Task 5: Integration verification

**Step 1: Build and deploy to test cluster**

**Step 2: Monitor for orphans**

```bash
kubectl exec -n autoforge <pod> -- bash -c '
  count=0
  for f in /proc/[0-9]*/status; do
    pid=$(grep "^Pid:" $f 2>/dev/null | awk "{print \$2}")
    ppid=$(grep "^PPid:" $f 2>/dev/null | awk "{print \$2}")
    if [ "$ppid" = "1" ] && [ "$pid" != "1" ]; then count=$((count+1)); fi
  done
  echo "$count orphaned processes"
'
```

Expected: 0 orphaned processes (or very few within grace period)

**Step 3: Check memory stability**

```bash
kubectl exec -n autoforge <pod> -- cat /sys/fs/cgroup/memory.current
```

Memory should stay stable rather than growing toward the 10Gi limit.
