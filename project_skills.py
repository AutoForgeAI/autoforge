"""
Project Skills
==============

Manage the Claude Code skills installed in a generated project's
``.claude/skills/`` directory.

Agents run with ``setting_sources=["project"]``, so only skills that live
inside the project are visible to them. This module lets users pick skills
from a library when a project is created (or later) and copies them in.

Skill library sources, in precedence order (first match for a name wins):

1. Bundled project skills: ``.claude/templates/skills/`` in AutoForge
2. Bundled AutoForge skills: ``.claude/skills/`` in AutoForge (excluding
   skills that only make sense for AutoForge itself)
3. User AutoForge library: ``~/.autoforge/skills/``
4. User's global Claude Code skills: ``~/.claude/skills/``

The special ``project-learnings`` skill is a living document the coding agent
updates after completing features (see ``prompts.get_learnings_section``).
"""

import re
import shutil
from pathlib import Path
from typing import Any

import yaml

AUTOFORGE_ROOT = Path(__file__).parent

# Skill that the coding agent keeps up to date with project learnings
LEARNINGS_SKILL_NAME = "project-learnings"

# Skills that are always installed by scaffolding and cannot be removed,
# because the prompts depend on them.
REQUIRED_SKILLS = frozenset({"playwright-cli"})

# Bundled skills that are meant for working on AutoForge, not generated apps
_EXCLUDED_BUNDLED_SKILLS = frozenset({"gsd-to-autoforge-spec"})

# Skill names become directory names, so keep them strict
_SKILL_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}$")

_MAX_DESCRIPTION_LENGTH = 500


def _library_sources() -> list[tuple[str, Path]]:
    """Return (source_label, directory) pairs in precedence order."""
    home = Path.home()
    return [
        ("bundled", AUTOFORGE_ROOT / ".claude" / "templates" / "skills"),
        ("bundled", AUTOFORGE_ROOT / ".claude" / "skills"),
        ("user", home / ".autoforge" / "skills"),
        ("claude", home / ".claude" / "skills"),
    ]


def is_valid_skill_name(name: str) -> bool:
    """Check that a skill name is safe to use as a directory name."""
    return bool(_SKILL_NAME_RE.match(name)) and ".." not in name


def get_project_skills_dir(project_dir: Path) -> Path:
    """Return the project's ``.claude/skills`` directory."""
    return project_dir / ".claude" / "skills"


def parse_skill_metadata(skill_md: Path) -> dict[str, str]:
    """Parse ``name`` and ``description`` from a SKILL.md YAML frontmatter.

    Returns an empty dict if the file has no readable frontmatter.
    """
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return {}

    match = re.match(r"^---\s*\n(.*?)\n---\s*(?:\n|$)", text, re.DOTALL)
    if not match:
        return {}

    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return {}
    if not isinstance(data, dict):
        return {}

    result: dict[str, str] = {}
    for key in ("name", "description"):
        value = data.get(key)
        if isinstance(value, str):
            result[key] = value.strip()
    if "description" in result:
        result["description"] = result["description"][:_MAX_DESCRIPTION_LENGTH]
    return result


def _iter_skill_dirs(root: Path):
    """Yield skill directories (containing SKILL.md) directly under root."""
    if not root.is_dir():
        return
    try:
        entries = sorted(root.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return
    for entry in entries:
        if entry.is_dir() and is_valid_skill_name(entry.name) and (entry / "SKILL.md").is_file():
            yield entry


def _skill_info(skill_dir: Path, source: str) -> dict[str, Any]:
    meta = parse_skill_metadata(skill_dir / "SKILL.md")
    return {
        "name": skill_dir.name,
        "description": meta.get("description", ""),
        "source": source,
        "required": skill_dir.name in REQUIRED_SKILLS,
        "recommended": skill_dir.name == LEARNINGS_SKILL_NAME,
    }


def _find_library_skill(name: str) -> tuple[str, Path] | None:
    """Locate a skill by name in the library. Returns (source, path) or None."""
    if not is_valid_skill_name(name):
        return None
    for source, root in _library_sources():
        if source == "bundled" and name in _EXCLUDED_BUNDLED_SKILLS:
            continue
        candidate = root / name
        if candidate.is_dir() and (candidate / "SKILL.md").is_file():
            return source, candidate
    return None


def list_library_skills() -> list[dict[str, Any]]:
    """List every skill available for installation into projects."""
    seen: set[str] = set()
    skills: list[dict[str, Any]] = []
    for source, root in _library_sources():
        for skill_dir in _iter_skill_dirs(root):
            name = skill_dir.name
            if name in seen:
                continue
            if source == "bundled" and name in _EXCLUDED_BUNDLED_SKILLS:
                continue
            seen.add(name)
            skills.append(_skill_info(skill_dir, source))
    return skills


def list_project_skills(project_dir: Path) -> list[dict[str, Any]]:
    """List the skills installed in a project."""
    return [_skill_info(d, "project") for d in _iter_skill_dirs(get_project_skills_dir(project_dir))]


def _ignore_unsafe(directory: str, names: list[str]) -> set[str]:
    """copytree ignore callback: skip symlinks and caches.

    Symlinks are skipped so that a skill in the user's home directory cannot
    pull files from elsewhere (e.g. credentials) into the project.
    """
    ignored = set()
    for name in names:
        if name in ("__pycache__", ".git") or Path(directory, name).is_symlink():
            ignored.add(name)
    return ignored


def install_skills(project_dir: Path, names: list[str]) -> tuple[list[str], list[str]]:
    """Copy skills from the library into the project.

    Skills that are already installed are left untouched (so agent-made
    edits, e.g. to project-learnings, are preserved).

    Returns:
        (installed, skipped) - names newly installed, and names that were
        unknown or already present.

    Raises:
        ValueError: If a name is not a valid skill name.
    """
    for name in names:
        if not is_valid_skill_name(name):
            raise ValueError(f"Invalid skill name: {name!r}")

    dest_root = get_project_skills_dir(project_dir)
    installed: list[str] = []
    skipped: list[str] = []
    for name in dict.fromkeys(names):  # dedupe, keep order
        found = _find_library_skill(name)
        dest = dest_root / name
        if found is None or dest.exists():
            skipped.append(name)
            continue
        _, src = found
        dest_root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src.resolve(), dest, ignore=_ignore_unsafe)
        installed.append(name)
    return installed, skipped


def remove_skill(project_dir: Path, name: str) -> bool:
    """Remove an installed skill from the project.

    Returns:
        True if removed, False if it was not installed.

    Raises:
        ValueError: If the name is invalid or the skill is required.
    """
    if not is_valid_skill_name(name):
        raise ValueError(f"Invalid skill name: {name!r}")
    if name in REQUIRED_SKILLS:
        raise ValueError(f"Skill '{name}' is required by AutoForge and cannot be removed")

    skills_dir = get_project_skills_dir(project_dir).resolve()
    target = skills_dir / name
    if target.is_symlink():
        target.unlink()
        return True
    if not target.is_dir():
        return False
    # Defense in depth: never delete outside the project's skills directory
    if target.resolve().parent != skills_dir:
        raise ValueError(f"Refusing to remove skill outside project: {name!r}")
    shutil.rmtree(target)
    return True


def has_learnings_skill(project_dir: Path) -> bool:
    """Whether the project has the self-improving project-learnings skill."""
    return (get_project_skills_dir(project_dir) / LEARNINGS_SKILL_NAME / "SKILL.md").is_file()
