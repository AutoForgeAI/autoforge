"""
Model Settings API Router
==========================

REST API endpoints for managing AI model selection settings.

Endpoints:
- GET /model-settings - Get current model settings
- PUT /model-settings - Update model settings
- POST /model-settings/preset - Apply a preset configuration
- GET /model-settings/presets - List available presets
"""

from pathlib import Path
from typing import List, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from autocoder.core.model_settings import ModelSettings, get_preset_info, parse_models_arg
from autocoder.agent.registry import get_project_path

router = APIRouter(prefix="/api/model-settings", tags=["model-settings"])


# Pydantic models for API
class ModelSettingsResponse(BaseModel):
    """Model settings response"""
    preset: str
    available_models: List[str]
    category_mapping: dict
    fallback_model: str
    auto_detect_simple: bool
    assistant_model: str | None = None


class UpdateSettingsRequest(BaseModel):
    """Request to update model settings"""
    preset: str | None = Field(None, description="Preset name (quality, balanced, economy, cheap, experimental)")
    available_models: List[str] | None = Field(None, description="List of available models (opus, sonnet, haiku)")
    auto_detect_simple: bool | None = Field(None, description="Enable auto-detection of simple tasks")
    assistant_model: Literal["opus", "sonnet", "haiku"] | None = Field(
        None, description="Optional assistant chat model override (opus, sonnet, haiku)"
    )


class ApplyPresetRequest(BaseModel):
    """Request to apply a preset"""
    preset: str = Field(..., description="Preset name to apply")


class PresetInfo(BaseModel):
    """Information about a preset"""
    name: str
    description: str
    models: List[str]
    best_for: str


class PresetsResponse(BaseModel):
    """Response with all presets"""
    presets: dict[str, PresetInfo]


def _resolve_project_dir(project: str | None) -> Path | None:
    if not project:
        return None
    name = project.strip()
    if not name:
        return None
    p = get_project_path(name)
    return p.resolve() if p else None


def _load_settings(project: str | None) -> ModelSettings:
    project_dir = _resolve_project_dir(project)
    if project_dir:
        return ModelSettings.load_for_project(project_dir)
    # Back-compat: if no project is provided, use global file defaults.
    settings_file = Path.home() / ".autocoder" / "model_settings.json"
    return ModelSettings.load(settings_file) if settings_file.exists() else ModelSettings()


def _save_settings(project: str | None, settings: ModelSettings) -> None:
    project_dir = _resolve_project_dir(project)
    if project_dir:
        settings.save_for_project(project_dir)
        return
    # Back-compat global file write.
    settings_file = Path.home() / ".autocoder" / "model_settings.json"
    settings.save(settings_file)


@router.get("", response_model=ModelSettingsResponse)
async def get_model_settings(project: str | None = None):
    """Get current model settings

    Returns the current model selection configuration including preset,
    available models, and category mappings.
    """
    settings = _load_settings(project)
    return ModelSettingsResponse(
        preset=settings.preset,
        available_models=settings.available_models,
        category_mapping=settings.category_mapping,
        fallback_model=settings.fallback_model,
        auto_detect_simple=settings.auto_detect_simple,
        assistant_model=settings.assistant_model,
    )


@router.put("")
async def update_model_settings(request: UpdateSettingsRequest, project: str | None = None):
    """Update model settings

    Update the model configuration. Can specify preset, available models,
    or auto-detect setting. Changes are persisted to disk.
    """
    settings = _load_settings(project)

    # Update available models if provided
    if request.available_models is not None:
        try:
            settings.set_custom_models(request.available_models)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Update preset if provided
    elif request.preset is not None:
        try:
            settings.set_preset(request.preset)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

    # Update auto-detect if provided
    if request.auto_detect_simple is not None:
        settings.auto_detect_simple = request.auto_detect_simple

    if request.assistant_model is not None:
        settings.assistant_model = request.assistant_model

    # Save settings
    _save_settings(project, settings)

    return {
        "success": True,
        "settings": ModelSettingsResponse(
            preset=settings.preset,
            available_models=settings.available_models,
            category_mapping=settings.category_mapping,
            fallback_model=settings.fallback_model,
            auto_detect_simple=settings.auto_detect_simple,
            assistant_model=settings.assistant_model,
        )
    }


@router.post("/preset")
async def apply_preset(request: ApplyPresetRequest, project: str | None = None):
    """Apply a preset configuration

    Applies a predefined preset configuration (quality, balanced, economy, cheap, experimental).
    This resets all settings to the preset's defaults.
    """
    settings = _load_settings(project)

    try:
        settings.set_preset(request.preset)
        _save_settings(project, settings)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "success": True,
        "message": f"Applied preset: {request.preset}",
        "settings": ModelSettingsResponse(
            preset=settings.preset,
            available_models=settings.available_models,
            category_mapping=settings.category_mapping,
            fallback_model=settings.fallback_model,
            auto_detect_simple=settings.auto_detect_simple,
            assistant_model=settings.assistant_model,
        )
    }


@router.get("/presets", response_model=PresetsResponse)
async def list_presets():
    """List all available presets

    Returns information about all available model selection presets
    including their names, descriptions, and best use cases.
    """
    presets_info = get_preset_info()

    return PresetsResponse(
        presets={
            preset: PresetInfo(
                name=info["name"],
                description=info["description"],
                models=info["models"],
                best_for=info["best_for"]
            )
            for preset, info in presets_info.items()
        }
    )


@router.post("/test")
async def test_model_selection(feature: dict):
    """Test model selection for a feature

    Given a feature (with category, description, name), returns which model
    would be selected based on current settings. Useful for previewing model selection.
    """
    settings = get_global_settings()
    selected_model = settings.select_model(feature)

    return {
        "feature": feature,
        "selected_model": selected_model,
        "settings": {
            "preset": settings.preset,
            "available_models": settings.available_models
        }
    }
