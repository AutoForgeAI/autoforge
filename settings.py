"""
Settings Storage Module
=======================

Handles app-level and project-level settings storage.

Storage locations:
- App-level: ~/.autocoder/settings.json
- Project-level: {project_dir}/.autocoder-config.json

Resolution order: Project config → App defaults → Built-in defaults
"""

import json
from pathlib import Path
from typing import Any

from agent_types import ModelConfig

# App-level settings location
APP_SETTINGS_DIR = Path.home() / ".autocoder"
APP_SETTINGS_FILE = APP_SETTINGS_DIR / "settings.json"

# Project-level settings filename
PROJECT_SETTINGS_FILENAME = ".autocoder-config.json"

# Available models for selection
AVAILABLE_MODELS = [
    {
        "id": "claude-opus-4-5-20251101",
        "name": "Claude Opus 4.5",
        "description": "Most capable, best for complex reasoning",
    },
    {
        "id": "claude-sonnet-4-5-20250929",
        "name": "Claude Sonnet 4.5",
        "description": "Balanced quality and speed",
    },
    {
        "id": "claude-3-5-haiku-20241022",
        "name": "Claude Haiku 3.5",
        "description": "Fast and cost-effective",
    },
]

# Built-in defaults (fallback)
BUILTIN_DEFAULTS = {
    "models": {
        "architect": "claude-opus-4-5-20251101",
        "initializer": "claude-opus-4-5-20251101",
        "coding": "claude-sonnet-4-5-20250929",
        "reviewer": "claude-sonnet-4-5-20250929",
        "testing": "claude-3-5-haiku-20241022",
    }
}


def _ensure_app_settings_dir() -> None:
    """Ensure the app settings directory exists."""
    APP_SETTINGS_DIR.mkdir(parents=True, exist_ok=True)


def get_app_settings() -> dict[str, Any]:
    """
    Load app-level settings from ~/.autocoder/settings.json.

    Returns built-in defaults if file doesn't exist.
    """
    _ensure_app_settings_dir()

    if not APP_SETTINGS_FILE.exists():
        return BUILTIN_DEFAULTS.copy()

    try:
        with open(APP_SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
            # Merge with defaults to ensure all keys exist
            result = BUILTIN_DEFAULTS.copy()
            if "models" in settings:
                result["models"] = {**result["models"], **settings["models"]}
            return result
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Could not load app settings: {e}")
        return BUILTIN_DEFAULTS.copy()


def save_app_settings(settings: dict[str, Any]) -> bool:
    """
    Save app-level settings to ~/.autocoder/settings.json.

    Returns True on success, False on failure.
    """
    _ensure_app_settings_dir()

    try:
        with open(APP_SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        return True
    except OSError as e:
        print(f"Error saving app settings: {e}")
        return False


def get_project_settings(project_dir: Path) -> dict[str, Any] | None:
    """
    Load project-level settings from {project_dir}/.autocoder-config.json.

    Returns None if no project settings exist (inherits from app defaults).
    """
    settings_file = project_dir / PROJECT_SETTINGS_FILENAME

    if not settings_file.exists():
        return None

    try:
        with open(settings_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Warning: Could not load project settings: {e}")
        return None


def save_project_settings(project_dir: Path, settings: dict[str, Any] | None) -> bool:
    """
    Save project-level settings to {project_dir}/.autocoder-config.json.

    If settings is None, removes the project settings file (inherit from app defaults).
    Returns True on success, False on failure.
    """
    settings_file = project_dir / PROJECT_SETTINGS_FILENAME

    if settings is None:
        # Remove project settings to inherit from app defaults
        if settings_file.exists():
            try:
                settings_file.unlink()
            except OSError as e:
                print(f"Error removing project settings: {e}")
                return False
        return True

    try:
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        return True
    except OSError as e:
        print(f"Error saving project settings: {e}")
        return False


def get_merged_model_config(project_dir: Path | None = None) -> dict[str, str]:
    """
    Get merged model configuration.

    Resolution order: Project config → App defaults → Built-in defaults

    Returns a dict with keys: architect, initializer, coding, reviewer, testing
    """
    # Start with built-in defaults
    merged = BUILTIN_DEFAULTS["models"].copy()

    # Override with app-level settings
    app_settings = get_app_settings()
    if "models" in app_settings:
        merged.update(app_settings["models"])

    # Override with project-level settings (if project specified)
    if project_dir is not None:
        project_settings = get_project_settings(project_dir)
        if project_settings and "models" in project_settings:
            merged.update(project_settings["models"])

    return merged


def get_model_config_for_project(project_dir: Path | None = None) -> ModelConfig:
    """
    Get a ModelConfig instance with merged settings for a project.

    This is the main entry point for getting model configuration when starting an agent.
    """
    merged = get_merged_model_config(project_dir)

    return ModelConfig(
        architect_model=merged.get("architect", BUILTIN_DEFAULTS["models"]["architect"]),
        initializer_model=merged.get("initializer", BUILTIN_DEFAULTS["models"]["initializer"]),
        coding_model=merged.get("coding", BUILTIN_DEFAULTS["models"]["coding"]),
        reviewer_model=merged.get("reviewer", BUILTIN_DEFAULTS["models"]["reviewer"]),
        testing_model=merged.get("testing", BUILTIN_DEFAULTS["models"]["testing"]),
    )


def has_project_settings(project_dir: Path) -> bool:
    """Check if a project has custom settings configured."""
    settings_file = project_dir / PROJECT_SETTINGS_FILENAME
    return settings_file.exists()


def get_settings_source(project_dir: Path | None = None) -> str:
    """
    Get a human-readable description of where settings are coming from.

    Returns: "Project", "App Defaults", or "Built-in Defaults"
    """
    if project_dir is not None:
        project_settings = get_project_settings(project_dir)
        if project_settings and "models" in project_settings:
            return "Project"

    if APP_SETTINGS_FILE.exists():
        return "App Defaults"

    return "Built-in Defaults"
