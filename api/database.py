"""
Database Models and Connection
==============================

SQLite database schema for feature storage using SQLAlchemy.
"""

import logging
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, Optional

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    """Return current UTC time. Replacement for deprecated _utc_now()."""
    return datetime.now(timezone.utc)

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    event,
    text,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, relationship, sessionmaker
from sqlalchemy.types import JSON


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 style declarative base."""
    pass


class Feature(Base):
    """Feature model representing a test case/feature to implement."""

    __tablename__ = "features"

    # Composite index for common status query pattern (passes, in_progress, needs_human_input)
    # Used by feature_get_stats, get_ready_features, and other status queries
    __table_args__ = (
        Index('ix_feature_status', 'passes', 'in_progress', 'needs_human_input'),
    )

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

    # Human input: agent can request structured input from a human
    needs_human_input = Column(Boolean, nullable=False, default=False, index=True)
    human_input_request = Column(JSON, nullable=True, default=None)   # Agent's structured request
    human_input_response = Column(JSON, nullable=True, default=None)  # Human's response

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
            # Human input fields
            "needs_human_input": self.needs_human_input if self.needs_human_input is not None else False,
            "human_input_request": self.human_input_request,
            "human_input_response": self.human_input_response,
        }

    def get_dependencies_safe(self) -> list[int]:
        """Safely extract dependencies, handling NULL and malformed data."""
        if self.dependencies is None:
            return []
        if isinstance(self.dependencies, list):
            return [d for d in self.dependencies if isinstance(d, int)]
        return []


class Schedule(Base):
    """Time-based schedule for automated agent start/stop."""

    __tablename__ = "schedules"

    # Database-level CHECK constraints for data integrity
    __table_args__ = (
        CheckConstraint('duration_minutes >= 1 AND duration_minutes <= 1440', name='ck_schedule_duration'),
        CheckConstraint('days_of_week >= 0 AND days_of_week <= 127', name='ck_schedule_days'),
        CheckConstraint('max_concurrency >= 1 AND max_concurrency <= 5', name='ck_schedule_concurrency'),
        CheckConstraint('crash_count >= 0', name='ck_schedule_crash_count'),
    )

    id = Column(Integer, primary_key=True, index=True)
    project_name = Column(String(50), nullable=False, index=True)

    # Timing (stored in UTC)
    start_time = Column(String(5), nullable=False)  # "HH:MM" format
    duration_minutes = Column(Integer, nullable=False)  # 1-1440

    # Day filtering (bitfield: Mon=1, Tue=2, Wed=4, Thu=8, Fri=16, Sat=32, Sun=64)
    days_of_week = Column(Integer, nullable=False, default=127)  # 127 = all days

    # State
    enabled = Column(Boolean, nullable=False, default=True, index=True)

    # Agent configuration for scheduled runs
    yolo_mode = Column(Boolean, nullable=False, default=False)
    model = Column(String(50), nullable=True)  # None = use global default
    max_concurrency = Column(Integer, nullable=False, default=3)  # 1-5 concurrent agents

    # Crash recovery tracking
    crash_count = Column(Integer, nullable=False, default=0)  # Resets at window start

    # Metadata
    created_at = Column(DateTime, nullable=False, default=_utc_now)

    # Relationships
    overrides = relationship(
        "ScheduleOverride", back_populates="schedule", cascade="all, delete-orphan"
    )

    def to_dict(self) -> dict:
        """Convert schedule to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "project_name": self.project_name,
            "start_time": self.start_time,
            "duration_minutes": self.duration_minutes,
            "days_of_week": self.days_of_week,
            "enabled": self.enabled,
            "yolo_mode": self.yolo_mode,
            "model": self.model,
            "max_concurrency": self.max_concurrency,
            "crash_count": self.crash_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def is_active_on_day(self, weekday: int) -> bool:
        """Check if schedule is active on given weekday (0=Monday, 6=Sunday)."""
        day_bit = 1 << weekday
        return bool(self.days_of_week & day_bit)


class ScheduleOverride(Base):
    """Persisted manual override for a schedule window."""

    __tablename__ = "schedule_overrides"

    id = Column(Integer, primary_key=True, index=True)
    schedule_id = Column(
        Integer, ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False
    )

    # Override details
    override_type = Column(String(10), nullable=False)  # "start" or "stop"
    expires_at = Column(DateTime, nullable=False)  # When this window ends (UTC)

    # Metadata
    created_at = Column(DateTime, nullable=False, default=_utc_now)

    # Relationships
    schedule = relationship("Schedule", back_populates="overrides")

    def to_dict(self) -> dict:
        """Convert override to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "schedule_id": self.schedule_id,
            "override_type": self.override_type,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


def get_database_path(project_dir: Path) -> Path:
    """Return the path to the SQLite database for a project."""
    from autoforge_paths import get_features_db_path
    return get_features_db_path(project_dir)


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


def _migrate_add_testing_columns(engine) -> None:
    """Legacy migration - no longer adds testing columns.

    The testing_in_progress and last_tested_at columns were removed from the
    Feature model as part of simplifying the testing agent architecture.
    Multiple testing agents can now test the same feature concurrently
    without coordination.

    This function is kept for backwards compatibility but does nothing.
    Existing databases with these columns will continue to work - the columns
    are simply ignored.
    """
    pass


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
        # Unix: Check mount type via /proc/mounts
        try:
            with open("/proc/mounts", "r") as f:
                mounts = f.read()
        except OSError:
            return False
        fs_type = _fs_type_for_path(path_str, mounts)
        if fs_type is not None and _is_unsafe_wal_fs_type(fs_type):
            return True

    return False


# Filesystems where SQLite's WAL mode is known to be unreliable: network
# filesystems (no coherent shared-memory/mmap across hosts) and VM/container
# host-share filesystems such as WSL's /mnt/c (9p/drvfs) or VirtualBox shares,
# where mmap of the -shm file typically fails with "disk I/O error".
_UNSAFE_WAL_FS_TYPES = frozenset({
    "nfs", "nfs4", "cifs", "smbfs", "smb3", "ncpfs", "afs", "coda",
    "9p", "drvfs", "v9fs", "vboxsf", "vmhgfs", "prl_fs", "virtiofs",
    "ceph", "glusterfs", "lustre", "gpfs", "ocfs2", "gfs2", "davfs",
})


def _is_unsafe_wal_fs_type(fs_type: str) -> bool:
    """Return True if WAL mode should not be used on this filesystem type."""
    if fs_type in _UNSAFE_WAL_FS_TYPES:
        return True
    # FUSE filesystems (sshfs, rclone, s3fs, gcsfuse, vmhgfs-fuse, ...) rarely
    # implement the shared mmap semantics WAL needs. Local FUSE filesystems
    # that are known to work fine are allowed.
    if fs_type == "fuseblk" or not fs_type.startswith("fuse"):
        return False
    return True


def _fs_type_for_path(path_str: str, mounts: str) -> Optional[str]:
    """Find the filesystem type of the mount containing ``path_str``.

    Args:
        path_str: Absolute, resolved POSIX path
        mounts: Contents of /proc/mounts

    Returns:
        The filesystem type of the longest matching mount point, or None.
    """
    best_mount: Optional[str] = None
    best_type: Optional[str] = None
    for line in mounts.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        # /proc/mounts escapes spaces, tabs, newlines and backslashes as octal
        mount_point = re.sub(r"\\([0-7]{3})", lambda m: chr(int(m.group(1), 8)), parts[1])
        fs_type = parts[2]
        # Match on path component boundaries so /mnt/c does not match /mnt/code
        prefix = mount_point.rstrip("/") + "/"
        if path_str != mount_point and not path_str.startswith(prefix):
            continue
        # Later entries with the same mount point shadow earlier ones
        if best_mount is None or len(mount_point) >= len(best_mount):
            best_mount = mount_point
            best_type = fs_type
    return best_type


def _is_wal_io_error(exc: BaseException) -> bool:
    """Return True if ``exc`` looks like SQLite failing to use WAL on this filesystem."""
    if not isinstance(exc, (sqlite3.OperationalError, OperationalError)):
        return False
    message = str(exc).lower()
    return "disk i/o error" in message or "locking protocol" in message


def _apply_journal_mode(engine, journal_mode: str) -> None:
    """Set the journal mode and verify the database is actually readable.

    PRAGMA journal_mode must run outside of a transaction, so this uses the
    raw DBAPI connection. The trailing schema read forces SQLite to open the
    WAL index (-shm), which is where unsupported filesystems fail.
    """
    with engine.connect() as conn:
        raw_conn = conn.connection.dbapi_connection
        if raw_conn is None:
            raise RuntimeError("Failed to get raw DBAPI connection")
        cursor = raw_conn.cursor()
        try:
            cursor.execute(f"PRAGMA journal_mode={journal_mode}")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("SELECT count(*) FROM sqlite_master").fetchall()
        finally:
            cursor.close()


def _has_wal_header(db_path: Path) -> bool:
    """Return True if the database file header says it is in WAL mode.

    Bytes 18 and 19 of the SQLite header are the file format write/read
    versions; both are 2 for WAL databases and 1 for rollback-journal ones.
    """
    try:
        with open(db_path, "rb") as f:
            header = f.read(20)
    except OSError:
        return False
    return len(header) == 20 and header.startswith(b"SQLite format 3\x00") and 2 in (header[18], header[19])


def _probe_wal_support(db_dir: Path) -> bool:
    """Check whether WAL mode works in ``db_dir`` using a throwaway database.

    Probing on a separate file means a shared features.db is never switched to
    WAL (and back) by every process that opens it on a filesystem where WAL
    doesn't work. Doing that while other processes have the database open
    causes "database is locked" in the new process and "disk I/O error" in the
    existing ones.
    """
    # Per-process file name so concurrent probes don't interfere with each other
    probe_path = db_dir / f".wal-probe-{os.getpid()}.db"
    supported = False
    try:
        conn = sqlite3.connect(str(probe_path), timeout=5)
        try:
            mode = conn.execute("PRAGMA journal_mode=WAL").fetchone()
            conn.execute("CREATE TABLE IF NOT EXISTS probe (x INTEGER)")
            conn.execute("SELECT count(*) FROM sqlite_master").fetchall()
            supported = mode is not None and str(mode[0]).lower() == "wal"
        finally:
            conn.close()
    except sqlite3.Error as e:
        logger.info("SQLite WAL probe failed in %s: %s", db_dir, e)
    finally:
        for suffix in ("", "-wal", "-shm", "-journal"):
            try:
                Path(f"{probe_path}{suffix}").unlink()
            except OSError:
                pass
    return supported


def _wal_supported(db_dir: Path) -> bool:
    """Return whether WAL works in ``db_dir``, probing once per directory per process."""
    key = db_dir.as_posix()
    if key not in _wal_support_cache:
        _wal_support_cache[key] = _probe_wal_support(db_dir)
    return _wal_support_cache[key]


# Cache of WAL probe results. Key: database directory (posix string)
_wal_support_cache: dict[str, bool] = {}


def _force_rollback_journal(db_path: Path) -> None:
    """Convert a database that is stuck in WAL mode back to DELETE mode.

    A database whose header says WAL cannot be opened normally on a filesystem
    without shared-memory support. In EXCLUSIVE locking mode SQLite keeps the
    WAL index in heap memory instead of the -shm file, which lets us open it
    and switch the journal mode.
    """
    if not db_path.exists():
        return
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        conn.execute("PRAGMA locking_mode=EXCLUSIVE")
        conn.execute("PRAGMA journal_mode=DELETE").fetchall()
        conn.execute("PRAGMA locking_mode=NORMAL")
        # Locking mode NORMAL only takes effect after the next access
        conn.execute("SELECT count(*) FROM sqlite_master").fetchall()
    finally:
        conn.close()


def _migrate_add_human_input_columns(engine) -> None:
    """Add human input columns to existing databases that don't have them."""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA table_info(features)"))
        columns = [row[1] for row in result.fetchall()]

        if "needs_human_input" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN needs_human_input BOOLEAN DEFAULT 0"))
        if "human_input_request" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN human_input_request TEXT DEFAULT NULL"))
        if "human_input_response" not in columns:
            conn.execute(text("ALTER TABLE features ADD COLUMN human_input_response TEXT DEFAULT NULL"))
        conn.commit()


def _migrate_add_schedules_tables(engine) -> None:
    """Create schedules and schedule_overrides tables if they don't exist."""
    from sqlalchemy import inspect

    inspector = inspect(engine)
    existing_tables = inspector.get_table_names()

    # Create schedules table if missing
    if "schedules" not in existing_tables:
        Schedule.__table__.create(bind=engine)  # type: ignore[attr-defined]

    # Create schedule_overrides table if missing
    if "schedule_overrides" not in existing_tables:
        ScheduleOverride.__table__.create(bind=engine)  # type: ignore[attr-defined]

    # Add crash_count column if missing (for upgrades)
    if "schedules" in existing_tables:
        columns = [c["name"] for c in inspector.get_columns("schedules")]
        if "crash_count" not in columns:
            with engine.connect() as conn:
                conn.execute(
                    text("ALTER TABLE schedules ADD COLUMN crash_count INTEGER DEFAULT 0")
                )
                conn.commit()

        # Add max_concurrency column if missing (for upgrades)
        if "max_concurrency" not in columns:
            with engine.connect() as conn:
                conn.execute(
                    text("ALTER TABLE schedules ADD COLUMN max_concurrency INTEGER DEFAULT 3")
                )
                conn.commit()


def _configure_sqlite_immediate_transactions(engine) -> None:
    """Configure engine for IMMEDIATE transactions via event hooks.

    Per SQLAlchemy docs: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html

    This replaces fragile pysqlite implicit transaction handling with explicit
    BEGIN IMMEDIATE at transaction start. Benefits:
    - Acquires write lock immediately, preventing stale reads
    - Works correctly regardless of prior ORM operations
    - Future-proof: won't break when pysqlite legacy mode is removed in Python 3.16
    """
    @event.listens_for(engine, "connect")
    def do_connect(dbapi_connection, connection_record):
        # Disable pysqlite's implicit transaction handling
        dbapi_connection.isolation_level = None

        # Set busy_timeout on raw connection before any transactions
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA busy_timeout=30000")
        finally:
            cursor.close()

    @event.listens_for(engine, "begin")
    def do_begin(conn):
        # Use IMMEDIATE for all transactions to prevent stale reads
        conn.exec_driver_sql("BEGIN IMMEDIATE")


def create_database(project_dir: Path) -> tuple:
    """
    Create database and return engine + session maker.

    Uses a cache to avoid creating new engines for each request, which improves
    performance by reusing database connections.

    Args:
        project_dir: Directory containing the project

    Returns:
        Tuple of (engine, SessionLocal)
    """
    cache_key = project_dir.as_posix()

    if cache_key in _engine_cache:
        return _engine_cache[cache_key]

    db_url = get_database_url(project_dir)

    # Ensure parent directory exists (for .autoforge/ layout)
    db_path = get_database_path(project_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Choose journal mode based on filesystem type
    # WAL mode doesn't work reliably on network filesystems and can cause corruption.
    # Filesystems we can't detect are probed on a throwaway file so the shared
    # features.db is never switched to WAL where WAL doesn't work.
    use_wal = not _is_network_path(project_dir) and _wal_supported(db_path.parent)
    journal_mode = "WAL" if use_wal else "DELETE"

    if not use_wal and _has_wal_header(db_path):
        # A database left in WAL mode (e.g. by an older version that crashed with
        # "disk I/O error") can't be opened normally without WAL support
        logger.warning("Converting %s from WAL to journal_mode=DELETE", db_path)
        try:
            _force_rollback_journal(db_path)
        except sqlite3.OperationalError as e:
            # Another process may hold the database; the retry below handles it
            logger.warning("Could not convert %s to journal_mode=DELETE yet: %s", db_path, e)

    engine = create_engine(db_url, connect_args={
        "check_same_thread": False,
        "timeout": 30  # Wait up to 30s for locks
    })

    # Set journal mode BEFORE configuring event hooks
    # PRAGMA journal_mode must run outside of a transaction, and our event hooks
    # start a transaction with BEGIN IMMEDIATE on every operation
    try:
        _apply_journal_mode(engine, journal_mode)
    except (sqlite3.OperationalError, OperationalError) as e:
        # Some filesystems (WSL /mnt/*, Docker/VM shares, FUSE mounts, ...) don't
        # support the shared memory WAL needs and fail with "disk I/O error".
        # Fall back to the rollback journal instead of failing to start.
        if not _is_wal_io_error(e):
            raise
        logger.warning(
            "SQLite failed to open %s in journal_mode=%s (%s); falling back to journal_mode=DELETE. "
            "This usually means the project is on a network, VM-shared or FUSE filesystem.",
            db_path, journal_mode, e,
        )
        _wal_support_cache[db_path.parent.as_posix()] = False
        engine.dispose()
        _force_rollback_journal(db_path)
        _apply_journal_mode(engine, "DELETE")

    # Configure IMMEDIATE transactions via event hooks AFTER setting PRAGMAs
    # This must happen before create_all() and migrations run
    _configure_sqlite_immediate_transactions(engine)

    Base.metadata.create_all(bind=engine)

    # Migrate existing databases
    _migrate_add_in_progress_column(engine)
    _migrate_fix_null_boolean_fields(engine)
    _migrate_add_dependencies_column(engine)
    _migrate_add_testing_columns(engine)
    _migrate_add_human_input_columns(engine)

    # Migrate to add schedules tables
    _migrate_add_schedules_tables(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Cache the engine and session maker
    _engine_cache[cache_key] = (engine, SessionLocal)

    return engine, SessionLocal


def dispose_engine(project_dir: Path) -> bool:
    """Dispose of and remove the cached engine for a project.

    This closes all database connections, releasing file locks on Windows.
    Should be called before deleting the database file.

    Returns:
        True if an engine was disposed, False if no engine was cached.
    """
    cache_key = project_dir.as_posix()

    if cache_key in _engine_cache:
        engine, _ = _engine_cache.pop(cache_key)
        engine.dispose()
        return True

    return False


# Global session maker - will be set when server starts
_session_maker: Optional[sessionmaker] = None

# Engine cache to avoid creating new engines for each request
# Key: project directory path (as posix string), Value: (engine, SessionLocal)
_engine_cache: dict[str, tuple] = {}


def set_session_maker(session_maker: sessionmaker) -> None:
    """Set the global session maker."""
    global _session_maker
    _session_maker = session_maker


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for FastAPI to get database session.

    Yields a database session and ensures it's closed after use.
    """
    if _session_maker is None:
        raise RuntimeError("Database not initialized. Call set_session_maker first.")

    db = _session_maker()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# =============================================================================
# Atomic Transaction Helpers for Parallel Mode
# =============================================================================
# These helpers prevent database corruption when multiple processes access the
# same SQLite database concurrently. They use IMMEDIATE transactions which
# acquire write locks at the start (preventing stale reads) and atomic
# UPDATE ... WHERE clauses (preventing check-then-modify races).


from contextlib import contextmanager


@contextmanager
def atomic_transaction(session_maker):
    """Context manager for atomic SQLite transactions.

    Acquires a write lock immediately via BEGIN IMMEDIATE (configured by
    engine event hooks), preventing stale reads in read-modify-write patterns.
    This is essential for preventing race conditions in parallel mode.

    Args:
        session_maker: SQLAlchemy sessionmaker

    Yields:
        SQLAlchemy session with automatic commit/rollback

    Example:
        with atomic_transaction(session_maker) as session:
            # All reads in this block are protected by write lock
            feature = session.query(Feature).filter(...).first()
            feature.priority = new_priority
            # Commit happens automatically on exit
    """
    session = session_maker()
    try:
        yield session
        session.commit()
    except Exception:
        try:
            session.rollback()
        except Exception:
            pass  # Don't let rollback failure mask original error
        raise
    finally:
        session.close()
