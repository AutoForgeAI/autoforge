"""
Skills Router
=============

API endpoints for the skill library and per-project Claude Code skills.

Skills installed into a project's ``.claude/skills/`` are loaded by the coding
agents (they run with ``setting_sources=["project"]``).
"""

import logging
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..schemas import SkillInfo, SkillInstallRequest, SkillInstallResponse
from ..utils.project_helpers import get_project_path as _get_project_path
from ..utils.validation import validate_project_name

# Add root to path for project_skills module import
_root = Path(__file__).parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from project_skills import (
    install_skills,
    list_library_skills,
    list_project_skills,
    remove_skill,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["skills"])


def _get_project_dir(project_name: str) -> Path:
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found: {project_dir}")
    return project_dir


@router.get("/skills", response_model=list[SkillInfo])
async def get_skill_library():
    """List skills available for installation into projects."""
    return [SkillInfo(**s) for s in list_library_skills()]


@router.get("/projects/{project_name}/skills", response_model=list[SkillInfo])
async def get_project_skills(project_name: str):
    """List skills installed in a project."""
    project_dir = _get_project_dir(project_name)
    return [SkillInfo(**s) for s in list_project_skills(project_dir)]


@router.post("/projects/{project_name}/skills", response_model=SkillInstallResponse)
async def add_project_skills(project_name: str, request: SkillInstallRequest):
    """Install library skills into a project. Already-installed skills are kept as-is."""
    project_dir = _get_project_dir(project_name)
    try:
        installed, skipped = install_skills(project_dir, request.names)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OSError as e:
        logger.exception("Failed to install skills into %s", project_name)
        raise HTTPException(status_code=500, detail=f"Failed to install skills: {e}")
    return SkillInstallResponse(
        installed=installed,
        skipped=skipped,
        skills=[SkillInfo(**s) for s in list_project_skills(project_dir)],
    )


@router.delete("/projects/{project_name}/skills/{skill_name}")
async def delete_project_skill(project_name: str, skill_name: str):
    """Remove a skill from a project."""
    project_dir = _get_project_dir(project_name)
    try:
        removed = remove_skill(project_dir, skill_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OSError as e:
        logger.exception("Failed to remove skill %s from %s", skill_name, project_name)
        raise HTTPException(status_code=500, detail=f"Failed to remove skill: {e}")
    if not removed:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_name}' is not installed")
    return {"success": True, "message": f"Removed skill '{skill_name}'"}
