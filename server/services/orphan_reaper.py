"""
Orphan Process Reaper
=====================

Periodic background task that kills orphaned processes (PPid=1) inside the
container that were spawned by AutoForge but survived agent shutdown.

This is a safety net for the process-group kill mechanism. It runs every
60 seconds and kills any chrome, node, esbuild, or npm processes that:
  1. Have PPid == 1 (reparented to init — they're orphans)
  2. Are NOT the main autoforge-bin or uvicorn process
  3. Have been orphaned for at least 30 seconds (grace period)

Only active on Linux (containers). No-op on macOS/Windows.

TODO: The reaper kills live orphans but cannot clean up zombie processes
(state Z). Zombies occur when terminated children are reparented to PID 1
but PID 1 never calls waitpid(). This happens in containerized deployments
where PID 1 is not a proper init (e.g. no tini/dumb-init). Zombies don't
consume memory but accumulate PID table entries. Known solutions:
  - Container-side: use tini or dumb-init as PID 1 (ENTRYPOINT ["tini", "--"])
  - Code-side: prctl(PR_SET_CHILD_SUBREAPER) to adopt orphans into this
    process, then reap via SIGCHLD + os.waitpid(-1, WNOHANG)
See: https://github.com/AutoForgeAI/autoforge/pull/222
"""

import asyncio
import logging
import os
import sys
import time

import psutil

logger = logging.getLogger(__name__)

# Process names that are known AutoForge children and safe to kill when orphaned
ORPHAN_TARGETS = {
    "chrome", "chrome_crashpad",      # Playwright browsers
    "chromium", "chromium_crashpad",
    "node", "esbuild",               # Dev servers, vitest, vite
    "npm", "npx",                    # Package manager wrappers
    "sh", "bash",                    # Shell wrappers from Bash tool
}

# Minimum age (seconds) before an orphan is eligible for kill
ORPHAN_GRACE_PERIOD = 30

# How often to run the reaper (seconds)
REAP_INTERVAL = 60

_reaper_task: asyncio.Task | None = None


def _find_and_kill_orphans() -> dict:
    """Scan for orphaned processes and kill them.

    Returns dict with stats: {killed: int, errors: int, scanned: int}
    """
    stats = {"killed": 0, "errors": 0, "scanned": 0}
    now = time.time()
    my_pid = os.getpid()

    for proc in psutil.process_iter(["pid", "ppid", "name", "create_time"]):
        try:
            info = proc.info
            stats["scanned"] += 1

            # Skip non-orphans (ppid != 1) and PID 1 itself
            if info["ppid"] != 1 or info["pid"] in (1, my_pid):
                continue

            # Skip processes not in our target list
            name = (info["name"] or "").lower()
            if name not in ORPHAN_TARGETS:
                continue

            # Skip recently created processes (grace period)
            age = now - (info["create_time"] or now)
            if age < ORPHAN_GRACE_PERIOD:
                continue

            # Kill the orphan
            logger.info(
                "Reaping orphan: PID %d (%s), age %.0fs",
                info["pid"], name, age,
            )
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=3)
                except psutil.TimeoutExpired:
                    proc.kill()
                stats["killed"] += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            stats["errors"] += 1

    return stats


async def _reaper_loop():
    """Background loop that periodically reaps orphans."""
    logger.info(
        "Orphan reaper started (interval=%ds, grace=%ds)",
        REAP_INTERVAL, ORPHAN_GRACE_PERIOD,
    )
    while True:
        await asyncio.sleep(REAP_INTERVAL)
        try:
            loop = asyncio.get_running_loop()
            stats = await loop.run_in_executor(None, _find_and_kill_orphans)
            if stats["killed"] > 0:
                logger.info("Orphan reaper: killed %d orphan(s)", stats["killed"])
        except Exception:
            logger.warning("Orphan reaper error", exc_info=True)


def start_reaper():
    """Start the orphan reaper background task. Only runs on Linux."""
    global _reaper_task
    if sys.platform != "linux":
        logger.debug("Orphan reaper skipped (not Linux)")
        return
    if _reaper_task is not None:
        return
    _reaper_task = asyncio.create_task(_reaper_loop())
    logger.info("Orphan reaper background task registered")


def stop_reaper():
    """Stop the orphan reaper."""
    global _reaper_task
    if _reaper_task:
        _reaper_task.cancel()
        _reaper_task = None
