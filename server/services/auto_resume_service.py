"""
Auto-Resume Service
===================

Monitors agent status and automatically restarts crashed agents
when the autoResume setting is enabled.

Uses exponential backoff to prevent rapid restart loops:
- 1st attempt: 10 seconds delay
- 2nd attempt: 30 seconds delay
- 3rd attempt: 90 seconds delay
- Max 3 attempts, then gives up

This service is activated when an agent is started via the UI/API
(not for scheduled agents, which have their own restart logic).
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

# Constants
MAX_CRASH_RETRIES = 3
CRASH_BACKOFF_BASE = 10  # seconds - 10s, 30s, 90s


class AutoResumeTracker:
    """
    Tracks crash recovery state for a single project.

    Created when an agent is started manually (not via scheduler).
    Removed when agent is stopped manually or max retries reached.
    """

    def __init__(
        self,
        project_name: str,
        project_dir: Path,
        yolo_mode: bool,
        model: str | None,
        max_concurrency: int,
        testing_agent_ratio: int,
    ):
        self.project_name = project_name
        self.project_dir = project_dir
        self.yolo_mode = yolo_mode
        self.model = model
        self.max_concurrency = max_concurrency
        self.testing_agent_ratio = testing_agent_ratio

        self.crash_count = 0
        self.last_crash: datetime | None = None
        self._status_callback: Callable[[str], Awaitable[None]] | None = None
        self._restart_task: asyncio.Task | None = None
        self._active = True

    async def handle_crash(self) -> bool:
        """
        Handle a crash event. Schedules a restart if within retry limits.

        Returns:
            True if restart is scheduled, False if max retries exceeded.
        """
        if not self._active:
            return False

        self.crash_count += 1
        self.last_crash = datetime.now()

        if self.crash_count > MAX_CRASH_RETRIES:
            logger.warning(
                f"[AutoResume] Max retries ({MAX_CRASH_RETRIES}) exceeded for "
                f"project '{self.project_name}'. Giving up."
            )
            return False

        # Calculate backoff delay: 10s, 30s, 90s
        delay = CRASH_BACKOFF_BASE * (3 ** (self.crash_count - 1))

        logger.info(
            f"[AutoResume] Agent crashed for '{self.project_name}'. "
            f"Scheduling restart in {delay}s (attempt {self.crash_count}/{MAX_CRASH_RETRIES})"
        )

        # Schedule restart
        self._restart_task = asyncio.create_task(self._delayed_restart(delay))
        return True

    async def _delayed_restart(self, delay: float):
        """Wait for delay then restart the agent."""
        try:
            await asyncio.sleep(delay)

            if not self._active:
                logger.info(f"[AutoResume] Restart cancelled for '{self.project_name}' (tracker deactivated)")
                return

            await self._do_restart()

        except asyncio.CancelledError:
            logger.info(f"[AutoResume] Restart cancelled for '{self.project_name}'")
            raise
        except Exception as e:
            logger.error(f"[AutoResume] Restart failed for '{self.project_name}': {e}")

    async def _do_restart(self):
        """Actually restart the agent."""
        from .process_manager import get_manager

        root_dir = Path(__file__).parent.parent.parent
        manager = get_manager(self.project_name, self.project_dir, root_dir)

        if manager.status in ("running", "paused"):
            logger.info(f"[AutoResume] Agent already running for '{self.project_name}', skipping restart")
            return

        logger.info(
            f"[AutoResume] Restarting agent for '{self.project_name}' "
            f"(yolo={self.yolo_mode}, model={self.model}, concurrency={self.max_concurrency})"
        )

        success, msg = await manager.start(
            yolo_mode=self.yolo_mode,
            model=self.model,
            max_concurrency=self.max_concurrency,
            testing_agent_ratio=self.testing_agent_ratio,
        )

        if success:
            logger.info(f"[AutoResume] Successfully restarted agent for '{self.project_name}'")
            # Re-register the status callback for the new process
            if self._status_callback:
                manager.add_status_callback(self._status_callback)
        else:
            logger.error(f"[AutoResume] Failed to restart agent for '{self.project_name}': {msg}")

    def set_status_callback(self, callback: Callable[[str], Awaitable[None]]):
        """Set the status callback to be re-registered after restart."""
        self._status_callback = callback

    def deactivate(self):
        """Deactivate the tracker (e.g., when agent is manually stopped)."""
        self._active = False
        if self._restart_task and not self._restart_task.done():
            self._restart_task.cancel()

    def reset_crash_count(self):
        """Reset crash count (e.g., when agent runs successfully for a while)."""
        self.crash_count = 0


# Global registry of auto-resume trackers per project
_trackers: dict[str, AutoResumeTracker] = {}


def get_auto_resume_enabled(project_dir: Path) -> bool:
    """Check if auto-resume is enabled in settings."""
    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from settings import SettingsManager

    manager = SettingsManager(project_path=project_dir)
    return manager.get("autoResume") is True


def register_auto_resume(
    project_name: str,
    project_dir: Path,
    yolo_mode: bool,
    model: str | None,
    max_concurrency: int,
    testing_agent_ratio: int,
) -> AutoResumeTracker | None:
    """
    Register a project for auto-resume monitoring.

    Called when an agent is started manually (not via scheduler).
    Returns the tracker if auto-resume is enabled, None otherwise.
    """
    # Check if auto-resume is enabled
    if not get_auto_resume_enabled(project_dir):
        logger.debug(f"[AutoResume] Disabled for '{project_name}', skipping registration")
        return None

    # Create or reset tracker
    tracker = AutoResumeTracker(
        project_name=project_name,
        project_dir=project_dir,
        yolo_mode=yolo_mode,
        model=model,
        max_concurrency=max_concurrency,
        testing_agent_ratio=testing_agent_ratio,
    )

    # Deactivate any existing tracker
    if project_name in _trackers:
        _trackers[project_name].deactivate()

    _trackers[project_name] = tracker
    logger.info(f"[AutoResume] Registered tracking for '{project_name}'")

    return tracker


def unregister_auto_resume(project_name: str):
    """
    Unregister a project from auto-resume monitoring.

    Called when an agent is stopped manually.
    """
    if project_name in _trackers:
        _trackers[project_name].deactivate()
        del _trackers[project_name]
        logger.info(f"[AutoResume] Unregistered tracking for '{project_name}'")


def get_tracker(project_name: str) -> AutoResumeTracker | None:
    """Get the auto-resume tracker for a project."""
    return _trackers.get(project_name)


async def handle_agent_crash(project_name: str) -> bool:
    """
    Handle an agent crash event.

    Called by the status change callback when agent status becomes "crashed".
    Returns True if auto-restart is scheduled.
    """
    tracker = _trackers.get(project_name)
    if not tracker:
        logger.debug(f"[AutoResume] No tracker for '{project_name}', not auto-restarting")
        return False

    return await tracker.handle_crash()


def cleanup_all_trackers():
    """Cleanup all trackers on shutdown."""
    for tracker in _trackers.values():
        tracker.deactivate()
    _trackers.clear()
