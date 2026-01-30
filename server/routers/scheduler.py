"""
Scheduler Router
================

API endpoints for smart scheduling and usage level tracking.
Exposes session/token usage levels and scheduling recommendations.
"""

import sys
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Add root to path for imports
ROOT_DIR = Path(__file__).parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from registry import get_project_path
from smart_scheduler import (
    get_scheduler,
    reset_scheduler,
)

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


# =============================================================================
# Schemas
# =============================================================================


class SessionUsageResponse(BaseModel):
    """Session usage details."""
    sessionId: str
    startedAt: str
    messagesSent: int
    messagesLimit: int
    messagesRemaining: int
    messagePercentUsed: float
    inputTokensUsed: int
    outputTokensUsed: int
    contextTokensUsed: int
    contextLimit: int
    contextRemaining: int
    contextPercentUsed: float
    featuresAttempted: int
    featuresCompleted: int


class UsageSnapshotResponse(BaseModel):
    """Current usage snapshot."""
    timestamp: str
    level: Literal["healthy", "moderate", "low", "critical"]
    strategy: Literal["full_speed", "completion_focus", "wind_down", "stop"]
    session: SessionUsageResponse
    overallPercentageUsed: float
    shouldContinue: bool
    recommendedConcurrency: int
    statusMessage: str


class RecordMessageRequest(BaseModel):
    """Request to record a message exchange."""
    inputTokens: int = 0
    outputTokens: int = 0
    contextTokens: int = 0


class RecordFeatureRequest(BaseModel):
    """Request to record a feature attempt."""
    completed: bool = False


class UpdateLimitsRequest(BaseModel):
    """Request to update session limits."""
    messagesLimit: int | None = None
    contextLimit: int | None = None


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/{project_name}/status", response_model=UsageSnapshotResponse)
async def get_scheduler_status(project_name: str):
    """Get current scheduler status and usage snapshot."""
    path_str = get_project_path(project_name)
    if not path_str:
        raise HTTPException(404, f"Project not found: {project_name}")

    scheduler = get_scheduler(project_name)
    snapshot = scheduler.get_snapshot()

    return UsageSnapshotResponse(
        timestamp=snapshot.timestamp.isoformat(),
        level=snapshot.level.value,
        strategy=snapshot.strategy.value,
        session=SessionUsageResponse(**snapshot.session.to_dict()),
        overallPercentageUsed=snapshot.overall_percentage_used,
        shouldContinue=snapshot.should_continue,
        recommendedConcurrency=snapshot.recommended_concurrency,
        statusMessage=scheduler.get_status_message(),
    )


@router.get("/{project_name}/level")
async def get_usage_level(project_name: str):
    """Get just the current usage level."""
    path_str = get_project_path(project_name)
    if not path_str:
        raise HTTPException(404, f"Project not found: {project_name}")

    scheduler = get_scheduler(project_name)
    level = scheduler.get_usage_level()
    strategy = scheduler.get_strategy()

    return {
        "level": level.value,
        "strategy": strategy.value,
        "shouldContinue": scheduler.should_allow_new_work(),
        "recommendedConcurrency": scheduler.get_recommended_concurrency(),
    }


@router.post("/{project_name}/record-message")
async def record_message(project_name: str, request: RecordMessageRequest):
    """Record a message exchange for tracking."""
    path_str = get_project_path(project_name)
    if not path_str:
        raise HTTPException(404, f"Project not found: {project_name}")

    scheduler = get_scheduler(project_name)
    scheduler.record_message(
        input_tokens=request.inputTokens,
        output_tokens=request.outputTokens,
        context_tokens=request.contextTokens,
    )

    return {
        "success": True,
        "level": scheduler.get_usage_level().value,
        "messagesRemaining": scheduler.session.remaining_messages(),
    }


@router.post("/{project_name}/record-feature")
async def record_feature(project_name: str, request: RecordFeatureRequest):
    """Record a feature implementation attempt."""
    path_str = get_project_path(project_name)
    if not path_str:
        raise HTTPException(404, f"Project not found: {project_name}")

    scheduler = get_scheduler(project_name)
    scheduler.record_feature_attempt(completed=request.completed)

    return {
        "success": True,
        "featuresAttempted": scheduler.session.features_attempted,
        "featuresCompleted": scheduler.session.features_completed,
    }


@router.post("/{project_name}/reset")
async def reset_session(project_name: str):
    """Reset the session tracking."""
    path_str = get_project_path(project_name)
    if not path_str:
        raise HTTPException(404, f"Project not found: {project_name}")

    reset_scheduler(project_name)
    scheduler = get_scheduler(project_name)

    return {
        "success": True,
        "sessionId": scheduler.session.session_id,
        "message": "Session reset successfully",
    }


@router.patch("/{project_name}/limits")
async def update_limits(project_name: str, request: UpdateLimitsRequest):
    """Update session limits (for different Claude plans)."""
    path_str = get_project_path(project_name)
    if not path_str:
        raise HTTPException(404, f"Project not found: {project_name}")

    scheduler = get_scheduler(project_name)

    if request.messagesLimit is not None:
        scheduler.session.messages_limit = request.messagesLimit

    if request.contextLimit is not None:
        scheduler.session.context_limit = request.contextLimit

    return {
        "success": True,
        "messagesLimit": scheduler.session.messages_limit,
        "contextLimit": scheduler.session.context_limit,
    }


@router.get("/all")
async def get_all_scheduler_status():
    """Get status of all active schedulers."""
    from smart_scheduler import get_all_schedulers

    schedulers = get_all_schedulers()
    result = {}

    for project_name, scheduler in schedulers.items():
        snapshot = scheduler.get_snapshot()
        result[project_name] = {
            "level": snapshot.level.value,
            "strategy": snapshot.strategy.value,
            "overallPercentageUsed": snapshot.overall_percentage_used,
            "shouldContinue": snapshot.should_continue,
        }

    return {"schedulers": result}
