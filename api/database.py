"""
Database Models and Connection
==============================

SQLite database schema for feature storage using SQLAlchemy.
"""

import sys
from pathlib import Path
from typing import Optional

from sqlalchemy import Boolean, Column, Integer, String, Text, create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import JSON

Base = declarative_base()


class Feature(Base):
    """Feature model representing a test case/feature to implement."""

    __tablename__ = "features"

    id = Column(Integer, primary_key=True, index=True)
    priority = Column(Integer, nullable=False, default=999, index=True)
    category = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    steps = Column(JSON, nullable=False)  # Stored as JSON array
    passes = Column(Boolean, nullable=False, default=False, index=True)
    in_progress = Column(Boolean, nullable=False, default=False, index=True)
    # Dependencies: list of feature IDs that must be completed before this feature
    # NULL/empty = no dependencies (backwards compatible)
    dependencies = Column(JSON, nullable=True, default=None)

    # Error Recovery: Track failures for retry logic and escalation
    failure_reason = Column(Text, nullable=True)  # Last failure reason
    failure_count = Column(Integer, nullable=False, default=0)  # Number of failed attempts
    last_failure_at = Column(Text, nullable=True)  # ISO timestamp of last failure

    # Quality Gates: Store quality check results
    quality_result = Column(JSON, nullable=True)  # {"passed": bool, "checks": {...}, "timestamp": "..."}

    def to_dict(self) -> dict:
        """Convert feature to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "priority": self.priority,
            "category": self.category,
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
            # Handle legacy NULL values gracefully - treat as False
            "passes": self.passes if self.passes is not None else False,
            "in_progress": self.in_progress if self.in_progress is not None else False,
            # Dependencies: NULL/empty treated as empty list for backwards compat
            "dependencies": self.dependencies if self.dependencies else [],
            # Error Recovery fields
            "failure_reason": self.failure_reason,
            "failure_count": self.failure_count if self.failure_count is not None else 0,
            "last_failure_at": self.last_failure_at,
            # Quality Gates field
            "quality_result": self.quality_result,
        }

    def get_dependencies_safe(self) -> list[int]:
        """Safely extract dependencies, handling NULL and malformed data."""
        if self.dependencies is None:
            return []
        if isinstance(self.dependencies, list):
            return [d for d in self.dependencies if isinstance(d, int)]
        return []


def get_database_path(project_dir: Path) -> Path:
    """Return the path to the SQLite database for a project."""
    return project_dir / "features.db"


def get_database_url(project_dir: Path) -> str:
    """Return the SQLAlchemy database URL for a project.

    Uses POSIX-style paths (forward slashes) for cross-platform compatibility.
    """
    db_path = get_database_path(project_dir)
    return f"sqlite:///{db_path.as_posix()}"


def _migrate_add_in_progress_column(engine) -> None:
    """Add in_progress column to existing databases that don't have it."""
    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("PRAGMA table_info(features)"))
        columns = [row[1] for row in result.fetchall()]

        if "in_progress" not in columns:
            # Add the column with default value
            conn.execute(text("ALTER TABLE features ADD COLUMN in_progress BOOLEAN DEFAULT 0"))
            conn.commit()


def _migrate_fix_null_boolean_fields(engine) -> None:
    """Fix NULL values in passes and in_progress columns."""
    with engine.connect() as conn:
        # Fix NULL passes values
        conn.execute(text("UPDATE features SET passes = 0 WHERE passes IS NULL"))
        # Fix NULL in_progress values
        conn.execute(text("UPDATE features SET in_progress = 0 WHERE in_progress IS NULL"))
        conn.commit()


def _migrate_add_dependencies_column(engine) -> None:
    """Add dependencies column to existing databases that don't have it.

    Uses NULL default for backwards compatibility - existing features
    without dependencies will have NULL which is treated as empty list.
    """
    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("PRAGMA table_info(features)"))
        columns = [row[1] for row in result.fetchall()]

        if "dependencies" not in columns:
            # Use TEXT for SQLite JSON storage, NULL default for backwards compat
            conn.execute(text("ALTER TABLE features ADD COLUMN dependencies TEXT DEFAULT NULL"))
            conn.commit()


def _migrate_add_error_recovery_columns(engine) -> None:
    """Add error recovery columns to existing databases.

    Columns added:
    - failure_reason: TEXT - last failure reason
    - failure_count: INTEGER - number of failed attempts
    - last_failure_at: TEXT - ISO timestamp of last failure
    """
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(features)"))
        columns = [row[1] for row in result.fetchall()]

        if "failure_reason" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN failure_reason TEXT DEFAULT NULL"))

        if "failure_count" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN failure_count INTEGER DEFAULT 0"))

        if "last_failure_at" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN last_failure_at TEXT DEFAULT NULL"))

        conn.commit()


def _migrate_add_quality_result_column(engine) -> None:
    """Add quality_result column to existing databases.

    Stores JSON with quality check results:
    {"passed": bool, "checks": {...}, "timestamp": "..."}
    """
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(features)"))
        columns = [row[1] for row in result.fetchall()]

        if "quality_result" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN quality_result TEXT DEFAULT NULL"))
            conn.commit()


def _is_network_path(path: Path) -> bool:
    """Detect if path is on a network filesystem.

    WAL mode doesn't work reliably on network filesystems (NFS, SMB, CIFS)
    and can cause database corruption. This function detects common network
    path patterns so we can fall back to DELETE mode.

    Args:
        path: The path to check

    Returns:
        True if the path appears to be on a network filesystem
    """
    path_str = str(path.resolve())

    if sys.platform == "win32":
        # Windows UNC paths: \\server\share or \\?\UNC\server\share
        if path_str.startswith("\\\\"):
            return True
        # Mapped network drives - check if the drive is a network drive
        try:
            import ctypes
            drive = path_str[:2]  # e.g., "Z:"
            if len(drive) == 2 and drive[1] == ":":
                # DRIVE_REMOTE = 4
                drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive + "\\")
                if drive_type == 4:  # DRIVE_REMOTE
                    return True
        except (AttributeError, OSError):
            pass
    else:
        # Unix: Check mount type via /proc/mounts or mount command
        try:
            with open("/proc/mounts", "r") as f:
                mounts = f.read()
                # Check each mount point to find which one contains our path
                for line in mounts.splitlines():
                    parts = line.split()
                    if len(parts) >= 3:
                        mount_point = parts[1]
                        fs_type = parts[2]
                        # Check if path is under this mount point and if it's a network FS
                        if path_str.startswith(mount_point):
                            if fs_type in ("nfs", "nfs4", "cifs", "smbfs", "fuse.sshfs"):
                                return True
        except (FileNotFoundError, PermissionError):
            pass

    return False


def create_database(project_dir: Path) -> tuple:
    """
    Create database and return engine + session maker.

    Args:
        project_dir: Directory containing the project

    Returns:
        Tuple of (engine, SessionLocal)
    """
    db_url = get_database_url(project_dir)
    engine = create_engine(db_url, connect_args={
        "check_same_thread": False,
        "timeout": 30  # Wait up to 30s for locks
    })
    Base.metadata.create_all(bind=engine)

    # Choose journal mode based on filesystem type
    # WAL mode doesn't work reliably on network filesystems and can cause corruption
    is_network = _is_network_path(project_dir)
    journal_mode = "DELETE" if is_network else "WAL"

    with engine.connect() as conn:
        conn.execute(text(f"PRAGMA journal_mode={journal_mode}"))
        conn.execute(text("PRAGMA busy_timeout=30000"))
        conn.commit()

    # Migrate existing databases
    _migrate_add_in_progress_column(engine)
    _migrate_fix_null_boolean_fields(engine)
    _migrate_add_dependencies_column(engine)
    _migrate_add_error_recovery_columns(engine)
    _migrate_add_quality_result_column(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, SessionLocal


# Global session maker - will be set when server starts
_session_maker: Optional[sessionmaker] = None


def set_session_maker(session_maker: sessionmaker) -> None:
    """Set the global session maker."""
    global _session_maker
    _session_maker = session_maker


def get_db() -> Session:
    """
    Dependency for FastAPI to get database session.

    Yields a database session and ensures it's closed after use.
    """
    if _session_maker is None:
        raise RuntimeError("Database not initialized. Call set_session_maker first.")

    db = _session_maker()
    try:
        yield db
    finally:
        db.close()
