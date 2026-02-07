"""
Research Database Models and Connection
=======================================

SQLite database schema for research agent findings storage using SQLAlchemy.
The research agent stores findings in SQLite before writing final markdown files.

Database location: {project_dir}/.planning/research.db

Document Types:
- STACK: Technology stack detection results
- ARCHITECTURE: System architecture and patterns
- STRUCTURE: Directory and module organization
- CONVENTIONS: Code style and naming conventions
- INTEGRATIONS: External integrations and APIs
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.types import JSON

Base = declarative_base()


def _utc_now() -> datetime:
    """Return current UTC time. Replacement for deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc)


# Valid document types for research findings
DOCUMENT_TYPES = frozenset({
    "STACK",
    "ARCHITECTURE",
    "STRUCTURE",
    "CONVENTIONS",
    "INTEGRATIONS",
})


class ResearchDocument(Base):
    """Research document model representing a finding from codebase analysis.

    Each document represents a discrete piece of research about the codebase,
    organized by document type and section. Multiple documents can exist for
    the same type/section combination, allowing the agent to refine findings
    over multiple analysis passes.
    """

    __tablename__ = "research_documents"

    # Composite index for efficient queries by document type and section
    __table_args__ = (
        Index('ix_research_doc_type_section', 'document_type', 'section'),
    )

    id = Column(Integer, primary_key=True, index=True)
    document_type = Column(String(50), nullable=False, index=True)
    section = Column(String(100), nullable=False, index=True)
    content = Column(Text, nullable=False)
    # List of file paths that informed this finding (stored as JSON array)
    source_files = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=_utc_now)
    updated_at = Column(DateTime, nullable=False, default=_utc_now, onupdate=_utc_now)

    def to_dict(self) -> dict:
        """Convert research document to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "document_type": self.document_type,
            "section": self.section,
            "content": self.content,
            "source_files": self.source_files if self.source_files else [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def get_source_files_safe(self) -> list[str]:
        """Safely extract source files, handling NULL and malformed data."""
        if self.source_files is None:
            return []
        if isinstance(self.source_files, list):
            return [f for f in self.source_files if isinstance(f, str)]
        return []


class ResearchProgress(Base):
    """Research progress model for tracking the research agent's state.

    Tracks which phase the research agent is in and overall progress metrics.
    Only one active progress record should exist per research session.
    """

    __tablename__ = "research_progress"

    id = Column(Integer, primary_key=True, index=True)
    # Research phase: scanning, analyzing, documenting, complete
    phase = Column(String(50), nullable=False, default="scanning", index=True)
    files_scanned = Column(Integer, nullable=False, default=0)
    findings_count = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=False, default=_utc_now)
    completed_at = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        """Convert research progress to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "phase": self.phase,
            "files_scanned": self.files_scanned,
            "findings_count": self.findings_count,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    def is_complete(self) -> bool:
        """Check if research is complete."""
        return bool(self.phase == "complete" and self.completed_at is not None)


def get_research_database_path(project_dir: Path) -> Path:
    """Return the path to the research SQLite database for a project.

    The database is stored in the .planning directory to keep research
    artifacts separate from the main features database.

    Args:
        project_dir: Root directory of the project

    Returns:
        Path to research.db file
    """
    return project_dir / ".planning" / "research.db"


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


# Cache for engines to avoid creating multiple engines for the same database
_engine_cache: dict[str, Engine] = {}


def get_research_engine(db_path: Path) -> Engine:
    """Get or create a SQLAlchemy engine for the research database.

    Engines are cached by path to avoid creating multiple connections
    to the same database. The engine is configured with appropriate
    settings for SQLite concurrent access.

    Args:
        db_path: Path to the research.db file

    Returns:
        SQLAlchemy Engine instance
    """
    # Normalize path for cache key
    cache_key = str(db_path.resolve())

    if cache_key in _engine_cache:
        return _engine_cache[cache_key]

    # Ensure parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db_url = f"sqlite:///{db_path.as_posix()}"
    engine = create_engine(
        db_url,
        connect_args={
            "check_same_thread": False,
            "timeout": 30  # Wait up to 30s for locks
        }
    )

    # Choose journal mode based on filesystem type
    # WAL mode doesn't work reliably on network filesystems
    is_network = _is_network_path(db_path.parent)
    journal_mode = "DELETE" if is_network else "WAL"

    with engine.connect() as conn:
        conn.execute(text(f"PRAGMA journal_mode={journal_mode}"))
        conn.execute(text("PRAGMA busy_timeout=30000"))
        conn.commit()

    _engine_cache[cache_key] = engine
    return engine


def get_research_session(db_path: Path) -> Session:
    """Get a new session for research database operations.

    Creates a new session bound to the engine for the given database path.
    The caller is responsible for closing the session when done.

    Args:
        db_path: Path to the research.db file

    Returns:
        SQLAlchemy Session instance

    Example:
        session = get_research_session(db_path)
        try:
            docs = session.query(ResearchDocument).all()
            # ... work with docs ...
            session.commit()
        finally:
            session.close()
    """
    engine = get_research_engine(db_path)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return SessionLocal()


def init_research_db(db_path: Path) -> tuple[Engine, sessionmaker]:
    """Initialize the research database with all tables.

    Creates the database file and all required tables if they don't exist.
    This should be called before any research operations.

    Args:
        db_path: Path to the research.db file

    Returns:
        Tuple of (engine, SessionLocal) for database operations
    """
    engine = get_research_engine(db_path)

    # Create all tables defined in Base
    Base.metadata.create_all(bind=engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, SessionLocal


def clear_engine_cache() -> None:
    """Clear the engine cache.

    Useful for testing or when database files are deleted/moved.
    Existing sessions from cached engines should be closed before calling this.
    """
    global _engine_cache
    for engine in _engine_cache.values():
        engine.dispose()
    _engine_cache = {}


def reset_research_db(db_path: Path) -> None:
    """Reset the research database for a fresh research session.

    Clears all existing research data (progress and documents) so that
    a new research run starts from scratch. This should be called when
    the research agent starts to ensure clean state.

    Args:
        db_path: Path to the research.db file
    """
    engine, SessionLocal = init_research_db(db_path)
    session = SessionLocal()
    try:
        # Delete all existing data
        session.query(ResearchProgress).delete()
        session.query(ResearchDocument).delete()
        session.commit()
    finally:
        session.close()
