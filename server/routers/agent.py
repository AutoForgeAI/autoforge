"""
Agent Router
============

API endpoints for agent control (start/stop/pause/resume).
Uses project registry for path lookups.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..schemas import (
    AgentActionResponse,
    AgentStartRequest,
    AgentStatus,
    ResearchActionResponse,
    ResearchStartRequest,
    ResearchStatus,
)
from ..services.chat_constants import ROOT_DIR
from ..services.process_manager import get_manager, get_research_manager
from ..utils.project_helpers import get_project_path as _get_project_path
from ..utils.validation import validate_project_name


def _get_settings_defaults() -> tuple[bool, str, int, str, bool, int]:
    """Get defaults from global settings.

    Returns:
        Tuple of (yolo_mode, model, testing_agent_ratio, testing_mode, playwright_headless, batch_size)
    """
    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from registry import DEFAULT_MODEL, get_all_settings

    settings = get_all_settings()
    yolo_mode = (settings.get("yolo_mode") or "false").lower() == "true"
    model = settings.get("api_model") or settings.get("model", DEFAULT_MODEL)

    # Parse testing agent settings with defaults
    try:
        testing_agent_ratio = int(settings.get("testing_agent_ratio", "1"))
    except (ValueError, TypeError):
        testing_agent_ratio = 1

    # Get testing mode (full, smart, minimal, off)
    testing_mode = settings.get("testing_mode", "full")

    playwright_headless = (settings.get("playwright_headless") or "true").lower() == "true"

    try:
        batch_size = int(settings.get("batch_size", "3"))
    except (ValueError, TypeError):
        batch_size = 3

    return yolo_mode, model, testing_agent_ratio, testing_mode, playwright_headless, batch_size


router = APIRouter(prefix="/api/projects/{project_name}/agent", tags=["agent"])


def get_project_manager(project_name: str):
    """Get the process manager for a project."""
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found: {project_dir}")

    return get_manager(project_name, project_dir, ROOT_DIR)


@router.get("/status", response_model=AgentStatus)
async def get_agent_status(project_name: str):
    """Get the current status of the agent for a project."""
    manager = get_project_manager(project_name)

    # Run healthcheck to detect crashed processes
    await manager.healthcheck()

    return AgentStatus(
        status=manager.status,
        pid=manager.pid,
        started_at=manager.started_at.isoformat() if manager.started_at else None,
        yolo_mode=manager.yolo_mode,
        model=manager.model,
        parallel_mode=manager.parallel_mode,
        max_concurrency=manager.max_concurrency,
        testing_agent_ratio=manager.testing_agent_ratio,
        testing_mode=getattr(manager, 'testing_mode', 'full'),
    )


@router.post("/start", response_model=AgentActionResponse)
async def start_agent(
    project_name: str,
    request: AgentStartRequest = AgentStartRequest(),
):
    """Start the agent for a project."""
    manager = get_project_manager(project_name)

    # Get defaults from global settings if not provided in request
    default_yolo, default_model, default_testing_ratio, default_testing_mode, playwright_headless, default_batch_size = _get_settings_defaults()

    yolo_mode = request.yolo_mode if request.yolo_mode is not None else default_yolo
    model = request.model if request.model else default_model
    max_concurrency = request.max_concurrency or 1
    testing_agent_ratio = request.testing_agent_ratio if request.testing_agent_ratio is not None else default_testing_ratio
    testing_mode = request.testing_mode if request.testing_mode else default_testing_mode

    batch_size = default_batch_size

    success, message = await manager.start(
        yolo_mode=yolo_mode,
        model=model,
        max_concurrency=max_concurrency,
        testing_agent_ratio=testing_agent_ratio,
        testing_mode=testing_mode,
        playwright_headless=playwright_headless,
        batch_size=batch_size,
    )

    # Notify scheduler of manual start (to prevent auto-stop during scheduled window)
    if success:
        from ..services.scheduler_service import get_scheduler
        project_dir = _get_project_path(project_name)
        if project_dir:
            get_scheduler().notify_manual_start(project_name, project_dir)

    return AgentActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )


@router.post("/stop", response_model=AgentActionResponse)
async def stop_agent(project_name: str):
    """Stop the agent for a project."""
    manager = get_project_manager(project_name)

    success, message = await manager.stop()

    # Notify scheduler of manual stop (to prevent auto-start during scheduled window)
    if success:
        from ..services.scheduler_service import get_scheduler
        project_dir = _get_project_path(project_name)
        if project_dir:
            get_scheduler().notify_manual_stop(project_name, project_dir)

    return AgentActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )


@router.post("/pause", response_model=AgentActionResponse)
async def pause_agent(project_name: str):
    """Pause the agent for a project."""
    manager = get_project_manager(project_name)

    success, message = await manager.pause()

    return AgentActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )


@router.post("/resume", response_model=AgentActionResponse)
async def resume_agent(project_name: str):
    """Resume a paused agent."""
    manager = get_project_manager(project_name)

    success, message = await manager.resume()

    return AgentActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )


# ============================================================================
# Research Agent Endpoints
# ============================================================================


def get_research_project_manager(project_name: str):
    """Get the research process manager for a project."""
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found: {project_dir}")

    return get_research_manager(project_name, project_dir, ROOT_DIR)


def _get_research_progress(project_dir: Path) -> dict:
    """Get research progress from the database.

    Returns:
        Dictionary with phase, files_scanned, findings_count, finalized, finalized_at
    """
    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from api.research_database import (
        ResearchProgress,
        get_research_database_path,
        get_research_session,
    )

    db_path = get_research_database_path(project_dir)
    if not db_path.exists():
        return {
            "phase": None,
            "files_scanned": 0,
            "findings_count": 0,
            "finalized": False,
            "finalized_at": None,
        }

    try:
        # Clear engine cache to ensure fresh connection
        from api.research_database import _engine_cache
        cache_key = str(db_path.resolve())
        if cache_key in _engine_cache:
            _engine_cache[cache_key].dispose()
            del _engine_cache[cache_key]

        session = get_research_session(db_path)
        try:
            # Force WAL checkpoint to see latest data from other processes (MCP server)
            from sqlalchemy import text
            session.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))

            progress = session.query(ResearchProgress).first()
            if progress:
                return {
                    "phase": progress.phase,
                    "files_scanned": progress.files_scanned,
                    "findings_count": progress.findings_count,
                    "finalized": progress.is_complete(),
                    "finalized_at": progress.completed_at,
                }
            return {
                "phase": None,
                "files_scanned": 0,
                "findings_count": 0,
                "finalized": False,
                "finalized_at": None,
            }
        finally:
            session.close()
    except Exception:
        return {
            "phase": None,
            "files_scanned": 0,
            "findings_count": 0,
            "finalized": False,
            "finalized_at": None,
        }


@router.get("/research/status", response_model=ResearchStatus)
async def get_research_status(project_name: str):
    """Get the current status of the research agent for a project."""
    manager = get_research_project_manager(project_name)
    project_dir = _get_project_path(project_name)

    # Run healthcheck to detect crashed processes
    await manager.healthcheck()

    # Get research progress from database
    progress = _get_research_progress(project_dir)

    return ResearchStatus(
        status=manager.status,
        pid=manager.pid,
        started_at=manager.started_at.isoformat() if manager.started_at else None,
        model=manager.model,
        phase=progress["phase"],
        files_scanned=progress["files_scanned"],
        findings_count=progress["findings_count"],
        finalized=progress["finalized"],
        finalized_at=progress["finalized_at"],
    )


@router.post("/start-research", response_model=ResearchActionResponse)
async def start_research_agent(
    project_name: str,
    request: ResearchStartRequest = ResearchStartRequest(),
):
    """Start the research agent for a project.

    The research agent analyzes the codebase structure and documents findings
    in the .planning/codebase/ directory. This is typically run before adding
    new features to an existing codebase.

    If project_dir is provided and the project is not yet registered,
    it will be automatically registered with the given directory.
    """
    # Check if project exists in registry
    project_dir = _get_project_path(project_name)

    if not project_dir:
        # Project not in registry - try to register it with provided project_dir
        if not request.project_dir:
            raise HTTPException(
                status_code=400,
                detail=f"Project '{project_name}' not found in registry. "
                       "Please provide project_dir to register it."
            )

        # Register the project
        import sys
        root = Path(__file__).parent.parent.parent
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        from registry import register_project

        project_path = Path(request.project_dir)
        if not project_path.exists():
            raise HTTPException(
                status_code=400,
                detail=f"Project directory does not exist: {request.project_dir}"
            )

        try:
            register_project(project_name, project_path)
            project_dir = project_path
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found: {project_dir}")

    # Reset research database BEFORE starting to ensure clean state
    # This avoids race conditions where API returns stale data
    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from api.research_database import (
        get_research_database_path,
        init_research_db,
        reset_research_db,
        clear_engine_cache,
    )

    # Clear engine cache first to ensure fresh connection
    clear_engine_cache()
    db_path = get_research_database_path(project_dir)
    init_research_db(db_path)
    reset_research_db(db_path)

    manager = get_research_manager(project_name, project_dir, ROOT_DIR)

    # Get default model from global settings if not provided
    _, default_model, _, _, _, _ = _get_settings_defaults()
    model = request.model if request.model else default_model

    success, message = await manager.start(model=model)

    return ResearchActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )


@router.post("/research/stop", response_model=ResearchActionResponse)
async def stop_research_agent(project_name: str):
    """Stop the research agent for a project."""
    manager = get_research_project_manager(project_name)

    success, message = await manager.stop()

    return ResearchActionResponse(
        success=success,
        status=manager.status,
        message=message,
    )
