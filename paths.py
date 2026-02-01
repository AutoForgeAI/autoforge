"""
Autocoder Path Management
=========================

Centralized path definitions for all autocoder-generated files.
All autocoder files live in .autocoder/ to keep the project root clean.

Structure:
    .autocoder/
    ├── prompts/
    │   ├── app_spec.txt
    │   ├── initializer_prompt.md
    │   ├── coding_prompt.md
    │   └── .spec_status.json
    ├── features.db
    ├── features.db-wal
    ├── features.db-shm
    ├── settings.json
    ├── .agent.control
    ├── .agent.orchestrator_status
    ├── .agent.lock
    └── .progress_cache
"""

from pathlib import Path

# Base directory name for all autocoder files
AUTOCODER_DIR = ".autocoder"


def get_autocoder_dir(project_dir: Path) -> Path:
    """Get the .autocoder directory for a project, creating if needed."""
    autocoder_dir = project_dir / AUTOCODER_DIR
    autocoder_dir.mkdir(parents=True, exist_ok=True)
    return autocoder_dir


def get_prompts_dir(project_dir: Path) -> Path:
    """Get the prompts directory (.autocoder/prompts/)."""
    prompts_dir = get_autocoder_dir(project_dir) / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    return prompts_dir


def get_database_path(project_dir: Path) -> Path:
    """Get the features database path (.autocoder/features.db)."""
    return get_autocoder_dir(project_dir) / "features.db"


def get_settings_path(project_dir: Path) -> Path:
    """Get the project settings path (.autocoder/settings.json)."""
    return get_autocoder_dir(project_dir) / "settings.json"


def get_control_file(project_dir: Path) -> Path:
    """Get the agent control file path (.autocoder/.agent.control)."""
    return get_autocoder_dir(project_dir) / ".agent.control"


def get_status_file(project_dir: Path) -> Path:
    """Get the orchestrator status file path (.autocoder/.agent.orchestrator_status)."""
    return get_autocoder_dir(project_dir) / ".agent.orchestrator_status"


def get_lock_file(project_dir: Path) -> Path:
    """Get the agent lock file path (.autocoder/.agent.lock)."""
    return get_autocoder_dir(project_dir) / ".agent.lock"


def get_progress_cache(project_dir: Path) -> Path:
    """Get the progress cache file path (.autocoder/.progress_cache)."""
    return get_autocoder_dir(project_dir) / ".progress_cache"


def get_app_spec_path(project_dir: Path) -> Path:
    """Get the app specification file path (.autocoder/prompts/app_spec.txt)."""
    return get_prompts_dir(project_dir) / "app_spec.txt"


def get_initializer_prompt_path(project_dir: Path) -> Path:
    """Get the initializer prompt path (.autocoder/prompts/initializer_prompt.md)."""
    return get_prompts_dir(project_dir) / "initializer_prompt.md"


def get_coding_prompt_path(project_dir: Path) -> Path:
    """Get the coding prompt path (.autocoder/prompts/coding_prompt.md)."""
    return get_prompts_dir(project_dir) / "coding_prompt.md"


def get_spec_status_path(project_dir: Path) -> Path:
    """Get the spec status file path (.autocoder/prompts/.spec_status.json)."""
    return get_prompts_dir(project_dir) / ".spec_status.json"


# Database related files (WAL mode)
def get_database_files(project_dir: Path) -> list[Path]:
    """Get all database-related files (main db + WAL files)."""
    autocoder_dir = get_autocoder_dir(project_dir)
    return [
        autocoder_dir / "features.db",
        autocoder_dir / "features.db-wal",
        autocoder_dir / "features.db-shm",
    ]


# Migration support - check old locations
def migrate_legacy_paths(project_dir: Path) -> list[str]:
    """
    Migrate files from old locations to .autocoder/.

    Returns list of files that were migrated.
    """
    import shutil

    migrated = []
    autocoder_dir = get_autocoder_dir(project_dir)
    prompts_dir = get_prompts_dir(project_dir)

    # Old locations -> New locations
    migrations = [
        # Database files
        (project_dir / "features.db", autocoder_dir / "features.db"),
        (project_dir / "features.db-wal", autocoder_dir / "features.db-wal"),
        (project_dir / "features.db-shm", autocoder_dir / "features.db-shm"),
        # Control files
        (project_dir / ".agent.control", autocoder_dir / ".agent.control"),
        (project_dir / ".agent.orchestrator_status", autocoder_dir / ".agent.orchestrator_status"),
        (project_dir / ".agent.lock", autocoder_dir / ".agent.lock"),
        (project_dir / ".progress_cache", autocoder_dir / ".progress_cache"),
    ]

    # Migrate individual files
    for old_path, new_path in migrations:
        if old_path.exists() and not new_path.exists():
            try:
                shutil.move(str(old_path), str(new_path))
                migrated.append(f"{old_path.name} -> .autocoder/{new_path.name}")
            except Exception as e:
                print(f"[migration] Failed to migrate {old_path}: {e}")

    # Migrate prompts directory
    old_prompts = project_dir / "prompts"
    if old_prompts.exists() and old_prompts.is_dir():
        for old_file in old_prompts.iterdir():
            new_file = prompts_dir / old_file.name
            if not new_file.exists():
                try:
                    shutil.move(str(old_file), str(new_file))
                    migrated.append(f"prompts/{old_file.name} -> .autocoder/prompts/{old_file.name}")
                except Exception as e:
                    print(f"[migration] Failed to migrate {old_file}: {e}")

        # Remove old prompts dir if empty
        try:
            if not any(old_prompts.iterdir()):
                old_prompts.rmdir()
                migrated.append("prompts/ (removed empty directory)")
        except Exception:
            pass

    if migrated:
        print(f"[migration] Migrated {len(migrated)} files to .autocoder/")
        for m in migrated:
            print(f"  - {m}")

    return migrated
