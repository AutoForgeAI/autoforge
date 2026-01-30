"""
Settings Router V2
==================

Unified settings API with proper separation of:
- App-level settings (global, stored in ~/.autocoder/)
- Project-level settings (per-project overrides)
- Effective settings (merged with source tracking)

This router provides the foundation for the redesigned Settings UI.
"""

import sys
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# Add root to path for imports
ROOT_DIR = Path(__file__).parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from registry import AVAILABLE_MODELS, DEFAULT_MODEL, get_project_path
from settings import (
    BUILT_IN_DEFAULTS,
    AppSettings,
    ProjectSettings,
    SettingsManager,
)

router = APIRouter(prefix="/api/settings/v2", tags=["settings-v2"])


# =============================================================================
# Schemas
# =============================================================================


class AppSettingsResponse(BaseModel):
    """Application-level settings."""
    # Model settings
    defaultModel: str = DEFAULT_MODEL
    coderModel: str = DEFAULT_MODEL
    testerModel: str = DEFAULT_MODEL
    initializerModel: str = DEFAULT_MODEL

    # Agent settings
    maxConcurrency: int = 3
    yoloMode: bool = False
    autoResume: bool = True
    pauseOnError: bool = True
    testingAgentRatio: int = 1

    # UI settings
    theme: str = "twitter"
    darkMode: bool = False
    showDebugPanel: bool = False
    debugPanelHeight: int = 288
    celebrateOnComplete: bool = True
    kanbanColumns: int = 3  # 3 or 4 columns in Kanban view

    # Git settings
    autoCommit: bool = False
    commitMessagePrefix: str = "[autocoder]"
    createPullRequests: bool = False


class AppSettingsUpdate(BaseModel):
    """Update app-level settings (partial)."""
    defaultModel: str | None = None
    coderModel: str | None = None
    testerModel: str | None = None
    initializerModel: str | None = None
    maxConcurrency: int | None = Field(None, ge=1, le=5)
    yoloMode: bool | None = None
    autoResume: bool | None = None
    pauseOnError: bool | None = None
    testingAgentRatio: int | None = Field(None, ge=0, le=3)
    theme: str | None = None
    darkMode: bool | None = None
    showDebugPanel: bool | None = None
    debugPanelHeight: int | None = Field(None, ge=100, le=800)
    celebrateOnComplete: bool | None = None
    kanbanColumns: int | None = Field(None, ge=3, le=4)
    autoCommit: bool | None = None
    commitMessagePrefix: str | None = None
    createPullRequests: bool | None = None


class ProjectSettingsResponse(BaseModel):
    """Project-level settings (overrides app settings)."""
    # Model overrides
    coderModel: str | None = None
    testerModel: str | None = None
    initializerModel: str | None = None

    # Agent overrides
    maxConcurrency: int | None = None
    yoloMode: bool | None = None
    testingAgentRatio: int | None = None

    # Project-specific
    testingDirectory: str | None = None
    autoCommit: bool | None = None


class ProjectSettingsUpdate(BaseModel):
    """Update project-level settings (partial)."""
    coderModel: str | None = None
    testerModel: str | None = None
    initializerModel: str | None = None
    maxConcurrency: int | None = Field(None, ge=1, le=5)
    yoloMode: bool | None = None
    testingAgentRatio: int | None = Field(None, ge=0, le=3)
    testingDirectory: str | None = None
    autoCommit: bool | None = None


class EffectiveSettingsResponse(BaseModel):
    """Merged settings with source tracking."""
    settings: dict[str, Any]
    sources: dict[str, Literal["project", "app", "default"]]


class SettingsCategoriesResponse(BaseModel):
    """Settings organized by category for UI."""
    models: dict[str, Any]
    agents: dict[str, Any]
    ui: dict[str, Any]
    git: dict[str, Any]
    sources: dict[str, str]


# =============================================================================
# Helper Functions
# =============================================================================


def _get_manager(project_name: str | None = None) -> SettingsManager:
    """Get settings manager with optional project context."""
    project_path = None
    if project_name:
        path_str = get_project_path(project_name)
        if path_str:
            project_path = Path(path_str)
    return SettingsManager(project_path=project_path)


def _settings_to_response(settings: dict, defaults: dict) -> dict:
    """Convert internal settings dict to response format."""
    return {
        "defaultModel": settings.get("defaultModel", defaults.get("defaultModel")),
        "coderModel": settings.get("coderModel", defaults.get("coderModel")),
        "testerModel": settings.get("testerModel", defaults.get("testerModel")),
        "initializerModel": settings.get("initializerModel", defaults.get("initializerModel")),
        "maxConcurrency": settings.get("maxConcurrency", defaults.get("maxConcurrency")),
        "yoloMode": settings.get("yoloMode", defaults.get("yoloMode")),
        "autoResume": settings.get("autoResume", defaults.get("autoResume")),
        "pauseOnError": settings.get("pauseOnError", defaults.get("pauseOnError")),
        "testingAgentRatio": settings.get("testingAgentRatio", 1),
        "theme": settings.get("theme", defaults.get("theme")),
        "darkMode": settings.get("darkMode", False),
        "showDebugPanel": settings.get("showDebugPanel", defaults.get("showDebugPanel")),
        "debugPanelHeight": settings.get("debugPanelHeight", 288),
        "celebrateOnComplete": settings.get("celebrateOnComplete", defaults.get("celebrateOnComplete")),
        "kanbanColumns": settings.get("kanbanColumns", 3),
        "autoCommit": settings.get("autoCommit", defaults.get("autoCommit")),
        "commitMessagePrefix": settings.get("commitMessagePrefix", defaults.get("commitMessagePrefix")),
        "createPullRequests": settings.get("createPullRequests", defaults.get("createPullRequests")),
    }


# =============================================================================
# App Settings Endpoints
# =============================================================================


@router.get("/app", response_model=AppSettingsResponse)
async def get_app_settings():
    """Get application-level settings."""
    app_settings = AppSettings()
    app_settings.load()

    return AppSettingsResponse(
        **_settings_to_response(app_settings.settings, BUILT_IN_DEFAULTS)
    )


@router.patch("/app", response_model=AppSettingsResponse)
async def update_app_settings(update: AppSettingsUpdate):
    """Update application-level settings."""
    app_settings = AppSettings()
    app_settings.load()

    # Apply updates (only non-None values)
    update_dict = update.model_dump(exclude_none=True)
    for key, value in update_dict.items():
        # Validate model IDs
        if key in ("defaultModel", "coderModel", "testerModel", "initializerModel"):
            valid_ids = [m["id"] for m in AVAILABLE_MODELS]
            if value not in valid_ids:
                raise HTTPException(400, f"Invalid model: {value}")
        app_settings.set(key, value)

    app_settings.save()

    return AppSettingsResponse(
        **_settings_to_response(app_settings.settings, BUILT_IN_DEFAULTS)
    )


# =============================================================================
# Project Settings Endpoints
# =============================================================================


@router.get("/project/{project_name}", response_model=ProjectSettingsResponse)
async def get_project_settings(project_name: str):
    """Get project-level settings (overrides only)."""
    path_str = get_project_path(project_name)
    if not path_str:
        raise HTTPException(404, f"Project not found: {project_name}")

    project_settings = ProjectSettings(project_path=Path(path_str))
    project_settings.load()

    return ProjectSettingsResponse(
        coderModel=project_settings.get("coderModel"),
        testerModel=project_settings.get("testerModel"),
        initializerModel=project_settings.get("initializerModel"),
        maxConcurrency=project_settings.get("maxConcurrency"),
        yoloMode=project_settings.get("yoloMode"),
        testingAgentRatio=project_settings.get("testingAgentRatio"),
        testingDirectory=project_settings.get("testingDirectory"),
        autoCommit=project_settings.get("autoCommit"),
    )


@router.patch("/project/{project_name}", response_model=ProjectSettingsResponse)
async def update_project_settings(project_name: str, update: ProjectSettingsUpdate):
    """Update project-level settings."""
    path_str = get_project_path(project_name)
    if not path_str:
        raise HTTPException(404, f"Project not found: {project_name}")

    project_settings = ProjectSettings(project_path=Path(path_str))
    project_settings.load()

    # Apply updates (only non-None values)
    update_dict = update.model_dump(exclude_none=True)
    for key, value in update_dict.items():
        # Validate model IDs
        if key in ("coderModel", "testerModel", "initializerModel"):
            valid_ids = [m["id"] for m in AVAILABLE_MODELS]
            if value not in valid_ids:
                raise HTTPException(400, f"Invalid model: {value}")
        project_settings.set(key, value)

    project_settings.save()

    return ProjectSettingsResponse(
        coderModel=project_settings.get("coderModel"),
        testerModel=project_settings.get("testerModel"),
        initializerModel=project_settings.get("initializerModel"),
        maxConcurrency=project_settings.get("maxConcurrency"),
        yoloMode=project_settings.get("yoloMode"),
        testingAgentRatio=project_settings.get("testingAgentRatio"),
        testingDirectory=project_settings.get("testingDirectory"),
        autoCommit=project_settings.get("autoCommit"),
    )


@router.delete("/project/{project_name}/{key}")
async def clear_project_setting(project_name: str, key: str):
    """Clear a project-level setting (fall back to app/default)."""
    path_str = get_project_path(project_name)
    if not path_str:
        raise HTTPException(404, f"Project not found: {project_name}")

    project_settings = ProjectSettings(project_path=Path(path_str))
    project_settings.load()

    deleted = project_settings.delete(key)
    if deleted:
        project_settings.save()

    return {"success": deleted, "key": key}


@router.post("/project/{project_name}/reset")
async def reset_project_settings(project_name: str):
    """Reset all project-level settings (clear all overrides)."""
    path_str = get_project_path(project_name)
    if not path_str:
        raise HTTPException(404, f"Project not found: {project_name}")

    project_settings = ProjectSettings(project_path=Path(path_str))
    project_settings.load()

    # Clear all settings
    keys_to_clear = list(project_settings.settings.keys())
    for key in keys_to_clear:
        project_settings.delete(key)

    project_settings.save()

    return {"success": True, "message": "All project settings reset", "keysCleared": len(keys_to_clear)}


@router.post("/app/reset")
async def reset_app_settings():
    """Reset all app-level settings to built-in defaults."""
    app_settings = AppSettings()
    app_settings.load()

    # Clear all settings (they will fall back to BUILT_IN_DEFAULTS)
    keys_to_clear = list(app_settings.settings.keys())
    for key in keys_to_clear:
        app_settings.delete(key)

    app_settings.save()

    return {"success": True, "message": "All app settings reset to defaults", "keysCleared": len(keys_to_clear)}


# =============================================================================
# Effective Settings Endpoints
# =============================================================================


@router.get("/effective", response_model=EffectiveSettingsResponse)
async def get_effective_settings_no_project():
    """Get effective settings without project context (app + defaults)."""
    manager = SettingsManager()
    effective = manager.get_effective_settings()

    # Build sources
    sources = {}
    for key in effective:
        sources[key] = manager.get_setting_source(key)

    return EffectiveSettingsResponse(settings=effective, sources=sources)


@router.get("/effective/{project_name}", response_model=EffectiveSettingsResponse)
async def get_effective_settings(project_name: str):
    """Get effective settings for a project (project + app + defaults)."""
    path_str = get_project_path(project_name)
    if not path_str:
        raise HTTPException(404, f"Project not found: {project_name}")

    manager = SettingsManager(project_path=Path(path_str))
    effective = manager.get_effective_settings()

    # Build sources
    sources = {}
    for key in effective:
        sources[key] = manager.get_setting_source(key)

    return EffectiveSettingsResponse(settings=effective, sources=sources)


@router.get("/categories/{project_name}", response_model=SettingsCategoriesResponse)
async def get_settings_by_category(project_name: str):
    """Get settings organized by category for the UI."""
    path_str = get_project_path(project_name)
    project_path = Path(path_str) if path_str else None

    manager = SettingsManager(project_path=project_path)
    effective = manager.get_effective_settings()

    # Build sources
    sources = {key: manager.get_setting_source(key) for key in effective}

    return SettingsCategoriesResponse(
        models={
            "defaultModel": effective.get("defaultModel"),
            "coderModel": effective.get("coderModel"),
            "testerModel": effective.get("testerModel"),
            "initializerModel": effective.get("initializerModel"),
        },
        agents={
            "maxConcurrency": effective.get("maxConcurrency"),
            "yoloMode": effective.get("yoloMode"),
            "autoResume": effective.get("autoResume"),
            "pauseOnError": effective.get("pauseOnError"),
            "testingAgentRatio": effective.get("testingAgentRatio", 1),
        },
        ui={
            "theme": effective.get("theme"),
            "darkMode": effective.get("darkMode", False),
            "showDebugPanel": effective.get("showDebugPanel"),
            "debugPanelHeight": effective.get("debugPanelHeight", 288),
            "celebrateOnComplete": effective.get("celebrateOnComplete"),
            "kanbanColumns": effective.get("kanbanColumns", 3),
        },
        git={
            "autoCommit": effective.get("autoCommit"),
            "commitMessagePrefix": effective.get("commitMessagePrefix"),
            "createPullRequests": effective.get("createPullRequests"),
        },
        sources=sources,
    )
