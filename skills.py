"""
Project Skills
==============

Claude Code skills (``.claude/skills/<name>/SKILL.md``) installed into
AutoForge projects. Agents run with ``setting_sources=["project"]``, so any
skill copied into a project's ``.claude/skills/`` directory is available to
every agent session in that project.

Two skill sources make up the library offered at project setup time:

1. Bundled: skills shipped with AutoForge in ``.claude/skills/``
2. User: skills the user drops into ``~/.autoforge/skills/<name>/SKILL.md``
   (a user skill overrides a bundled skill with the same name)

The special ``project-learnings`` skill is generated from a template rather
than copied. When it is present in a project, coding agents are told to
reflect after each completed feature and record what they learned in it, so
the skill improves over the life of the project.
"""

import re
import shutil
from pathlib import Path
from typing import Any

import yaml

# Bundled skills shipped with AutoForge
BUNDLED_SKILLS_DIR = Path(__file__).parent / ".claude" / "skills"

# Template for the self-improving project learnings skill
LEARNINGS_TEMPLATE = Path(__file__).parent / ".claude" / "templates" / "project_learnings_skill.template.md"

LEARNINGS_SKILL_NAME = "project-learnings"

# Bundled skills that are never offered in the picker:
# - playwright-cli is always installed by scaffold_project_prompts()
# - gsd-to-autoforge-spec is for driving AutoForge itself, not for project agents
HIDDEN_BUNDLED_SKILLS = {"playwright-cli", "gsd-to-autoforge-spec"}

# Skills that are pre-selected in the project setup picker
DEFAULT_SKILLS = [LEARNINGS_SKILL_NAME]

# Same rule Claude Code applies to skill names
_SKILL_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")

_LEARNINGS_DESCRIPTION = (
    "Lessons learned while building this project, recorded by AutoForge agents "
    "after each completed feature. Read before implementing a feature."
)


def is_valid_skill_name(name: str) -> bool:
    """Return True if ``name`` is a safe skill directory name."""
    return bool(_SKILL_NAME_RE.match(name))


def get_user_skills_dir() -> Path:
    """Get the user's skill library directory (~/.autoforge/skills/)."""
    from registry import get_config_dir
    return get_config_dir() / "skills"


def get_project_skills_dir(project_dir: Path) -> Path:
    """Get the directory Claude Code loads project skills from."""
    return project_dir / ".claude" / "skills"


def _parse_frontmatter(skill_md: Path) -> dict[str, Any]:
    """Parse the YAML frontmatter of a SKILL.md file. Returns {} on failure."""
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    try:
        data = yaml.safe_load(text[3:end])
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def _describe_skill(skill_dir: Path, source: str) -> dict[str, Any] | None:
    """Build a skill info dict for a skill directory, or None if it isn't one."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_dir.is_dir() or not skill_md.is_file():
        return None
    if not is_valid_skill_name(skill_dir.name):
        return None
    meta = _parse_frontmatter(skill_md)
    description = meta.get("description")
    return {
        "name": skill_dir.name,
        "description": " ".join(str(description).split()) if description else "",
        "source": source,
    }


def _scan_skills_dir(directory: Path, source: str) -> dict[str, dict[str, Any]]:
    skills: dict[str, dict[str, Any]] = {}
    if not directory.is_dir():
        return skills
    for child in sorted(directory.iterdir()):
        info = _describe_skill(child, source)
        if info:
            skills[info["name"]] = info
    return skills


def _library_skill_dirs() -> dict[str, Path]:
    """Map skill name -> source directory for every copyable library skill."""
    dirs: dict[str, Path] = {}
    if BUNDLED_SKILLS_DIR.is_dir():
        for child in BUNDLED_SKILLS_DIR.iterdir():
            if child.name not in HIDDEN_BUNDLED_SKILLS and (child / "SKILL.md").is_file():
                dirs[child.name] = child
    user_dir = get_user_skills_dir()
    if user_dir.is_dir():
        for child in user_dir.iterdir():
            if (child / "SKILL.md").is_file():
                dirs[child.name] = child
    return {name: path for name, path in dirs.items() if is_valid_skill_name(name)}


def list_available_skills() -> list[dict[str, Any]]:
    """List skills that can be installed into a project.

    Returns:
        Skill info dicts with ``name``, ``description``, ``source``
        ("autoforge" for the generated learnings skill, "bundled" or "user")
        and ``default`` (pre-selected in the setup picker).
    """
    skills: dict[str, dict[str, Any]] = {
        LEARNINGS_SKILL_NAME: {
            "name": LEARNINGS_SKILL_NAME,
            "description": _LEARNINGS_DESCRIPTION,
            "source": "autoforge",
        }
    }
    bundled = _scan_skills_dir(BUNDLED_SKILLS_DIR, "bundled")
    for name in HIDDEN_BUNDLED_SKILLS:
        bundled.pop(name, None)
    skills.update(bundled)
    # User skills override bundled ones, but never the generated learnings skill
    user = _scan_skills_dir(get_user_skills_dir(), "user")
    user.pop(LEARNINGS_SKILL_NAME, None)
    skills.update(user)

    result = []
    for name in sorted(skills, key=lambda n: (n != LEARNINGS_SKILL_NAME, n)):
        info = skills[name]
        info["default"] = name in DEFAULT_SKILLS
        result.append(info)
    return result


def list_project_skills(project_dir: Path) -> list[dict[str, Any]]:
    """List skills installed in a project's ``.claude/skills/`` directory."""
    return list(_scan_skills_dir(get_project_skills_dir(project_dir), "project").values())


def ensure_learnings_skill(project_dir: Path) -> bool:
    """Create the project-learnings skill if the project doesn't have it.

    Returns:
        True if the skill was created, False if it already existed or
        could not be created.
    """
    dest_dir = get_project_skills_dir(project_dir) / LEARNINGS_SKILL_NAME
    dest = dest_dir / "SKILL.md"
    if dest.exists() or not LEARNINGS_TEMPLATE.exists():
        return False
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(LEARNINGS_TEMPLATE, dest)
    except (OSError, PermissionError) as e:
        print(f"  Warning: Could not create {LEARNINGS_SKILL_NAME} skill: {e}")
        return False
    return True


def has_learnings_skill(project_dir: Path) -> bool:
    """Return True if the project has the self-improving learnings skill."""
    return (get_project_skills_dir(project_dir) / LEARNINGS_SKILL_NAME / "SKILL.md").is_file()


def install_skills(project_dir: Path, names: list[str]) -> tuple[list[str], list[str]]:
    """Install library skills into a project.

    Skills already present in the project are left untouched, so any
    project-specific edits (including agent-written learnings) survive.

    Args:
        project_dir: The project directory
        names: Skill names from list_available_skills()

    Returns:
        (installed, unknown): names that were newly installed, and names
        that don't match any library skill.
    """
    library = _library_skill_dirs()
    skills_dir = get_project_skills_dir(project_dir)
    installed: list[str] = []
    unknown: list[str] = []

    for name in dict.fromkeys(names):  # de-duplicate, keep order
        if name == LEARNINGS_SKILL_NAME:
            if ensure_learnings_skill(project_dir):
                installed.append(name)
            continue
        src = library.get(name)
        if src is None:
            unknown.append(name)
            continue
        dest = skills_dir / name
        if dest.exists():
            continue
        try:
            skills_dir.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
            installed.append(name)
        except (OSError, PermissionError) as e:
            print(f"  Warning: Could not install skill {name}: {e}")

    return installed, unknown
