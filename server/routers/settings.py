"""
Settings Router
===============

API endpoints for app-level and project-level settings management.
"""

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException

from registry import get_project_path
from settings import (
    AVAILABLE_MODELS,
    get_app_settings,
    get_merged_model_config,
    get_project_settings,
    get_settings_source,
    has_project_settings,
    save_app_settings,
    save_project_settings,
)

from ..schemas import (
    AppSettingsResponse,
    AvailableModel,
    MergedSettingsResponse,
    ModelConfigSchema,
    ProjectSettingsResponse,
    SettingsUpdateRequest,
)

router = APIRouter(prefix="/api", tags=["settings"])


# ============================================================================
# Helper Functions
# ============================================================================

def _validate_project_name(name: str) -> str:
    """Validate project name format."""
    if not name or not re.match(r"^[\w\-]+$", name):
        raise HTTPException(status_code=400, detail="Invalid project name")
    return name


def _get_project_path(project_name: str) -> Path | None:
    """Get project path from registry."""
    return get_project_path(project_name)


# ============================================================================
# App-Level Settings Endpoints
# ============================================================================

@router.get("/settings", response_model=AppSettingsResponse)
async def get_app_settings_endpoint():
    """Get app-level default settings."""
    settings = get_app_settings()

    # Build available models list
    available = [
        AvailableModel(id=m["id"], name=m["name"], description=m["description"])
        for m in AVAILABLE_MODELS
    ]

    return AppSettingsResponse(
        models=ModelConfigSchema(**settings["models"]),
        available_models=available,
    )


@router.put("/settings", response_model=AppSettingsResponse)
async def update_app_settings_endpoint(request: SettingsUpdateRequest):
    """Update app-level default settings."""
    settings = {
        "models": request.models.model_dump()
    }

    success = save_app_settings(settings)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save settings")

    # Return updated settings
    return await get_app_settings_endpoint()


@router.get("/settings/models", response_model=list[AvailableModel])
async def get_available_models():
    """Get list of available models for selection."""
    return [
        AvailableModel(id=m["id"], name=m["name"], description=m["description"])
        for m in AVAILABLE_MODELS
    ]


# ============================================================================
# Project-Level Settings Endpoints
# ============================================================================

@router.get("/projects/{project_name}/settings", response_model=ProjectSettingsResponse)
async def get_project_settings_endpoint(project_name: str):
    """Get project-specific settings."""
    project_name = _validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found: {project_dir}")

    project_settings = get_project_settings(project_dir)
    has_custom = has_project_settings(project_dir)
    source = get_settings_source(project_dir)

    if project_settings and "models" in project_settings:
        return ProjectSettingsResponse(
            has_custom_settings=has_custom,
            models=ModelConfigSchema(**project_settings["models"]),
            source=source,
        )

    return ProjectSettingsResponse(
        has_custom_settings=has_custom,
        models=None,
        source=source,
    )


@router.put("/projects/{project_name}/settings", response_model=ProjectSettingsResponse)
async def update_project_settings_endpoint(
    project_name: str,
    request: SettingsUpdateRequest | None = None,
):
    """
    Update project-specific settings.

    If request body is empty or null, removes project settings (inherit from app defaults).
    """
    project_name = _validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found: {project_dir}")

    if request is None:
        # Remove project settings
        success = save_project_settings(project_dir, None)
    else:
        # Save project settings
        settings = {"models": request.models.model_dump()}
        success = save_project_settings(project_dir, settings)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to save project settings")

    # Return updated settings
    return await get_project_settings_endpoint(project_name)


@router.delete("/projects/{project_name}/settings")
async def delete_project_settings_endpoint(project_name: str):
    """Remove project-specific settings (inherit from app defaults)."""
    project_name = _validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found: {project_dir}")

    success = save_project_settings(project_dir, None)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to remove project settings")

    return {"success": True, "message": "Project settings removed"}


@router.get("/projects/{project_name}/settings/merged", response_model=MergedSettingsResponse)
async def get_merged_settings_endpoint(project_name: str):
    """
    Get merged settings for a project.

    Resolution order: Project config → App defaults → Built-in defaults
    """
    project_name = _validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found")

    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found: {project_dir}")

    merged = get_merged_model_config(project_dir)
    source = get_settings_source(project_dir)

    return MergedSettingsResponse(
        models=ModelConfigSchema(**merged),
        source=source,
    )
