"""
Logging Configuration
=====================

Centralized logging setup for the autocoder server.
- File-based logging with rotation
- 24-hour retention with automatic cleanup
- Structured formatting for easy debugging
"""

import logging
import os
import sys
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Default log directory: ~/.autocoder/logs/
DEFAULT_LOG_DIR = Path.home() / ".autocoder" / "logs"

# Log retention period in hours
LOG_RETENTION_HOURS = 24

# Max log file size before rotation (10 MB)
MAX_LOG_SIZE = 10 * 1024 * 1024

# Number of backup files to keep per log type
BACKUP_COUNT = 5


def get_log_dir() -> Path:
    """Get the log directory, creating it if needed."""
    log_dir = Path(os.environ.get("AUTOCODER_LOG_DIR", str(DEFAULT_LOG_DIR)))
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def cleanup_old_logs(log_dir: Path, retention_hours: int = LOG_RETENTION_HOURS) -> int:
    """
    Remove log files older than retention period.

    Returns the number of files deleted.
    """
    cutoff_time = datetime.now() - timedelta(hours=retention_hours)
    deleted = 0

    try:
        for log_file in log_dir.glob("*.log*"):
            try:
                # Check file modification time
                mtime = datetime.fromtimestamp(log_file.stat().st_mtime)
                if mtime < cutoff_time:
                    log_file.unlink()
                    deleted += 1
            except (OSError, IOError):
                pass  # Skip files we can't access
    except Exception:
        pass  # Don't fail startup on cleanup errors

    return deleted


def setup_logging(
    level: int = logging.INFO,
    log_dir: Path | None = None,
    include_console: bool = True,
) -> Path:
    """
    Configure logging for the autocoder server.

    Creates three log files:
    - server.log: All server logs (INFO+)
    - error.log: Errors only (WARNING+)
    - agent.log: Agent subprocess output

    Args:
        level: Minimum log level
        log_dir: Directory for log files (default: ~/.autocoder/logs/)
        include_console: Also log to console

    Returns:
        Path to the log directory
    """
    if log_dir is None:
        log_dir = get_log_dir()
    else:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

    # Clean up old logs on startup
    deleted = cleanup_old_logs(log_dir)
    if deleted > 0:
        print(f"[logging] Cleaned up {deleted} old log file(s)", flush=True)

    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    simple_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Handler 1: Main server log (all INFO+)
    server_log = log_dir / "server.log"
    server_handler = RotatingFileHandler(
        server_log,
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    server_handler.setLevel(logging.INFO)
    server_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(server_handler)

    # Handler 2: Error log (WARNING+)
    error_log = log_dir / "error.log"
    error_handler = RotatingFileHandler(
        error_log,
        maxBytes=MAX_LOG_SIZE,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.WARNING)
    error_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(error_handler)

    # Handler 3: Console (if enabled)
    if include_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(simple_formatter)
        root_logger.addHandler(console_handler)

    # Log startup
    logging.info(f"Logging initialized - log directory: {log_dir}")

    return log_dir


def get_agent_logger(project_name: str | None = None) -> logging.Logger:
    """
    Get a logger for agent output.

    This creates a separate log file for agent subprocess output.
    """
    log_dir = get_log_dir()

    if project_name:
        logger_name = f"agent.{project_name}"
        log_file = log_dir / f"agent_{project_name}.log"
    else:
        logger_name = "agent"
        log_file = log_dir / "agent.log"

    logger = logging.getLogger(logger_name)

    # Check if handler already exists
    if not logger.handlers:
        handler = RotatingFileHandler(
            log_file,
            maxBytes=MAX_LOG_SIZE,
            backupCount=BACKUP_COUNT,
            encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(
            fmt="%(asctime)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        # Prevent propagation to root logger (avoids duplicate console output)
        logger.propagate = False

    return logger


def log_agent_output(line: str, project_name: str | None = None) -> None:
    """Log a line of agent output to the agent log file."""
    logger = get_agent_logger(project_name)
    logger.info(line.rstrip())


def get_log_files() -> dict[str, Path]:
    """Get paths to all log files."""
    log_dir = get_log_dir()
    return {
        "server": log_dir / "server.log",
        "error": log_dir / "error.log",
        "agent": log_dir / "agent.log",
        "directory": log_dir,
    }


def tail_log(log_name: str = "server", lines: int = 100) -> list[str]:
    """
    Read the last N lines from a log file.

    Args:
        log_name: "server", "error", or "agent"
        lines: Number of lines to return

    Returns:
        List of log lines (most recent last)
    """
    log_files = get_log_files()
    log_path = log_files.get(log_name)

    if not log_path or not log_path.exists():
        return []

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            # Read all lines and return the last N
            all_lines = f.readlines()
            return [line.rstrip() for line in all_lines[-lines:]]
    except Exception:
        return []
