"""
Skills Router
=============

API endpoint listing the Claude Code skills that can be installed into
projects (bundled with AutoForge or placed in ~/.autoforge/skills/).
"""

import sys
from pathlib import Path

from fastapi import APIRouter

from ..schemas import SkillInfo

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("", response_model=list[SkillInfo])
async def list_skills():
    """List skills available to install into a project."""
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from skills import list_available_skills
    return list_available_skills()
