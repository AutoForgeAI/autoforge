"""
Browser View Service
====================

Captures periodic screenshots from active playwright-cli browser sessions
and streams them to the UI via WebSocket callbacks.

Each agent gets an isolated browser session (e.g., coding-5, testing-0).
This service polls those sessions with `playwright-cli screenshot` and
delivers the frames to subscribed UI clients.
"""

import asyncio
import base64
import logging
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Awaitable, Callable

logger = logging.getLogger(__name__)

POLL_INTERVAL = 2.0  # seconds between screenshot captures
BACKOFF_INTERVAL = 10.0  # seconds after repeated failures
MAX_FAILURES_BEFORE_BACKOFF = 10
MAX_FAILURES_BEFORE_STOP = 90  # ~3 minutes at normal rate before giving up
SCREENSHOT_TIMEOUT = 5  # seconds


@dataclass
class SessionInfo:
    """Metadata for an active browser session."""
    session_name: str
    agent_index: int
    agent_type: str  # "coding" or "testing"
    feature_id: int
    feature_name: str
    consecutive_failures: int = 0
    stopped: bool = False


@dataclass
class ScreenshotData:
    """A captured screenshot ready for delivery."""
    session_name: str
    agent_index: int
    agent_type: str
    feature_id: int
    feature_name: str
    image_base64: str  # base64-encoded PNG
    timestamp: str


class BrowserViewService:
    """Manages screenshot capture for active agent browser sessions.

    Follows the same singleton-per-project pattern as DevServerProcessManager.
    """

    def __init__(self, project_name: str, project_dir: Path):
        self.project_name = project_name
        self.project_dir = project_dir
        self._active_sessions: dict[str, SessionInfo] = {}
        self._subscribers = 0
        self._poll_task: asyncio.Task | None = None
        self._screenshot_callbacks: set[Callable[[ScreenshotData], Awaitable[None]]] = set()
        self._lock = asyncio.Lock()
        self._playwright_cli: str | None = None

    def _get_playwright_cli(self) -> str | None:
        """Find playwright-cli executable."""
        if self._playwright_cli is not None:
            return self._playwright_cli
        path = shutil.which("playwright-cli")
        if path:
            self._playwright_cli = path
        else:
            logger.warning("playwright-cli not found in PATH; browser view disabled")
        return self._playwright_cli

    async def register_session(
        self,
        session_name: str,
        agent_index: int,
        agent_type: str,
        feature_id: int,
        feature_name: str,
    ) -> None:
        """Register an agent's browser session for screenshot capture."""
        async with self._lock:
            self._active_sessions[session_name] = SessionInfo(
                session_name=session_name,
                agent_index=agent_index,
                agent_type=agent_type,
                feature_id=feature_id,
                feature_name=feature_name,
            )
            logger.debug("Registered browser session: %s", session_name)

    async def unregister_session(self, session_name: str) -> None:
        """Unregister a browser session when agent completes."""
        async with self._lock:
            removed = self._active_sessions.pop(session_name, None)
            if removed:
                logger.debug("Unregistered browser session: %s", session_name)
                # Clean up screenshot file
                self._cleanup_screenshot_file(session_name)

    def add_screenshot_callback(self, callback: Callable[[ScreenshotData], Awaitable[None]]) -> None:
        self._screenshot_callbacks.add(callback)

    def remove_screenshot_callback(self, callback: Callable[[ScreenshotData], Awaitable[None]]) -> None:
        self._screenshot_callbacks.discard(callback)

    async def add_subscriber(self) -> None:
        """Called when a UI client wants browser screenshots."""
        async with self._lock:
            self._subscribers += 1
            if self._subscribers == 1:
                self._start_polling()

    async def remove_subscriber(self) -> None:
        """Called when a UI client stops wanting screenshots."""
        async with self._lock:
            self._subscribers = max(0, self._subscribers - 1)
            if self._subscribers == 0:
                self._stop_polling()

    async def stop(self) -> None:
        """Clean up all sessions and stop polling."""
        async with self._lock:
            for session_name in list(self._active_sessions):
                self._cleanup_screenshot_file(session_name)
            self._active_sessions.clear()
            self._stop_polling()

    def _start_polling(self) -> None:
        """Start the screenshot polling loop."""
        if self._poll_task is not None and not self._poll_task.done():
            return
        self._poll_task = asyncio.create_task(self._poll_loop())
        logger.info("Started browser screenshot polling for %s", self.project_name)

    def _stop_polling(self) -> None:
        """Stop the screenshot polling loop."""
        if self._poll_task is not None and not self._poll_task.done():
            self._poll_task.cancel()
            self._poll_task = None
            logger.info("Stopped browser screenshot polling for %s", self.project_name)

    async def _poll_loop(self) -> None:
        """Main polling loop - capture screenshots for all active sessions."""
        try:
            while True:
                async with self._lock:
                    sessions = list(self._active_sessions.values())

                if sessions and self._screenshot_callbacks:
                    # Capture screenshots with limited concurrency
                    sem = asyncio.Semaphore(3)

                    async def capture_with_sem(session: SessionInfo) -> None:
                        async with sem:
                            await self._capture_and_deliver(session)

                    await asyncio.gather(
                        *(capture_with_sem(s) for s in sessions if not s.stopped),
                        return_exceptions=True,
                    )

                await asyncio.sleep(POLL_INTERVAL)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.warning("Browser screenshot polling crashed", exc_info=True)

    async def _capture_and_deliver(self, session: SessionInfo) -> None:
        """Capture a screenshot for a session and deliver to callbacks."""
        cli = self._get_playwright_cli()
        if not cli:
            return

        # Determine interval based on failure count
        if session.consecutive_failures >= MAX_FAILURES_BEFORE_BACKOFF:
            # In backoff mode - only capture every BACKOFF_INTERVAL/POLL_INTERVAL polls
            # We achieve this by checking a simple modulo on failure count
            if session.consecutive_failures % int(BACKOFF_INTERVAL / POLL_INTERVAL) != 0:
                return

        screenshot_dir = self.project_dir / ".playwright-cli"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = screenshot_dir / f"_view_{session.session_name}.png"

        try:
            proc = await asyncio.create_subprocess_exec(
                cli, "-s", session.session_name, "screenshot",
                f"--filename={screenshot_path}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.project_dir),
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=SCREENSHOT_TIMEOUT)

            if proc.returncode != 0:
                session.consecutive_failures += 1
                if session.consecutive_failures >= MAX_FAILURES_BEFORE_STOP:
                    session.stopped = True
                    logger.debug(
                        "Stopped polling session %s after %d failures",
                        session.session_name, session.consecutive_failures,
                    )
                return

            # Read and encode the screenshot
            if not screenshot_path.exists():
                session.consecutive_failures += 1
                return

            image_bytes = screenshot_path.read_bytes()
            image_base64 = base64.b64encode(image_bytes).decode("ascii")

            # Reset failure counter on success
            session.consecutive_failures = 0
            # Re-enable if previously stopped
            session.stopped = False

            screenshot = ScreenshotData(
                session_name=session.session_name,
                agent_index=session.agent_index,
                agent_type=session.agent_type,
                feature_id=session.feature_id,
                feature_name=session.feature_name,
                image_base64=image_base64,
                timestamp=datetime.now().isoformat(),
            )

            # Deliver to all callbacks
            for callback in list(self._screenshot_callbacks):
                try:
                    await callback(screenshot)
                except Exception:
                    pass  # Connection may be closed

        except asyncio.TimeoutError:
            session.consecutive_failures += 1
        except Exception:
            session.consecutive_failures += 1
        finally:
            # Clean up the screenshot file
            try:
                screenshot_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _cleanup_screenshot_file(self, session_name: str) -> None:
        """Remove a session's screenshot file."""
        try:
            path = self.project_dir / ".playwright-cli" / f"_view_{session_name}.png"
            path.unlink(missing_ok=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Global instance management (thread-safe)
# ---------------------------------------------------------------------------

_services: dict[tuple[str, str], BrowserViewService] = {}
_services_lock = threading.Lock()


def get_browser_view_service(project_name: str, project_dir: Path) -> BrowserViewService:
    """Get or create a BrowserViewService for a project (thread-safe)."""
    with _services_lock:
        key = (project_name, str(project_dir.resolve()))
        if key not in _services:
            _services[key] = BrowserViewService(project_name, project_dir)
        return _services[key]
