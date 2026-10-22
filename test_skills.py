"""
Project Skills Tests
====================

Tests for the skill library (skills.py), the learnings-skill prompt
injection (prompts.py), and the skills API endpoints.

Run with: python -m pytest test_skills.py -v
"""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import skills
from prompts import get_coding_prompt, get_single_feature_prompt, get_testing_prompt


@pytest.fixture
def user_skills(tmp_path, monkeypatch):
    """Point the user skill library at a temp dir and return it."""
    lib = tmp_path / "user_skills"
    lib.mkdir()
    monkeypatch.setattr(skills, "get_user_skills_dir", lambda: lib)
    return lib


def _make_skill(parent: Path, name: str, description: str = "A test skill") -> Path:
    skill_dir = parent / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: |\n  {description}\n  second line\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    return skill_dir


def test_list_available_skills_defaults(user_skills):
    available = skills.list_available_skills()
    names = [s["name"] for s in available]

    # Learnings skill is first and pre-selected
    assert names[0] == skills.LEARNINGS_SKILL_NAME
    assert available[0]["default"] is True
    assert available[0]["source"] == "autoforge"

    # Bundled skill offered; internal ones hidden
    assert "frontend-design" in names
    for hidden in skills.HIDDEN_BUNDLED_SKILLS:
        assert hidden not in names


def test_user_skills_listed_and_descriptions_flattened(user_skills):
    _make_skill(user_skills, "my-stack", "Use our house stack")
    (user_skills / "not-a-skill").mkdir()  # no SKILL.md
    _make_skill(user_skills, "Bad Name")  # invalid name

    by_name = {s["name"]: s for s in skills.list_available_skills()}
    assert by_name["my-stack"]["source"] == "user"
    assert by_name["my-stack"]["description"] == "Use our house stack second line"
    assert by_name["my-stack"]["default"] is False
    assert "not-a-skill" not in by_name
    assert "Bad Name" not in by_name


def test_user_cannot_override_learnings_skill(user_skills):
    _make_skill(user_skills, skills.LEARNINGS_SKILL_NAME, "hijack")
    by_name = {s["name"]: s for s in skills.list_available_skills()}
    assert by_name[skills.LEARNINGS_SKILL_NAME]["source"] == "autoforge"


def test_install_skills(tmp_path, user_skills):
    _make_skill(user_skills, "my-stack")
    project = tmp_path / "proj"
    project.mkdir()

    installed, unknown = skills.install_skills(
        project, ["my-stack", "frontend-design", skills.LEARNINGS_SKILL_NAME, "nope", "my-stack"]
    )
    assert installed == ["my-stack", "frontend-design", skills.LEARNINGS_SKILL_NAME]
    assert unknown == ["nope"]

    skills_dir = project / ".claude" / "skills"
    assert (skills_dir / "my-stack" / "SKILL.md").is_file()
    assert (skills_dir / "frontend-design" / "SKILL.md").is_file()
    assert skills.has_learnings_skill(project)

    installed_names = {s["name"] for s in skills.list_project_skills(project)}
    assert {"my-stack", "frontend-design", skills.LEARNINGS_SKILL_NAME} <= installed_names


def test_install_does_not_overwrite_existing(tmp_path, user_skills):
    _make_skill(user_skills, "my-stack")
    project = tmp_path / "proj"
    learnings = project / ".claude" / "skills" / skills.LEARNINGS_SKILL_NAME / "SKILL.md"
    learnings.parent.mkdir(parents=True)
    learnings.write_text("agent-written learnings", encoding="utf-8")

    installed, _ = skills.install_skills(project, [skills.LEARNINGS_SKILL_NAME])
    assert installed == []
    assert learnings.read_text(encoding="utf-8") == "agent-written learnings"


def test_learnings_instructions_only_when_skill_installed(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()

    assert "PROJECT LEARNINGS" not in get_coding_prompt(project)

    skills.ensure_learnings_skill(project)
    assert "PROJECT LEARNINGS" in get_coding_prompt(project)
    assert "PROJECT LEARNINGS" in get_coding_prompt(project, yolo_mode=True)
    assert "PROJECT LEARNINGS" in get_single_feature_prompt(1, project)
    # Testing agents only verify; they don't write learnings
    assert "PROJECT LEARNINGS" not in get_testing_prompt(project, testing_feature_id=1)


def test_learnings_template_has_valid_frontmatter():
    meta = skills._parse_frontmatter(skills.LEARNINGS_TEMPLATE)
    assert meta["name"] == skills.LEARNINGS_SKILL_NAME
    assert meta["description"]


def test_skills_api(user_skills):
    from server.routers.projects import router as projects_router
    from server.routers.skills import router as skills_router

    app = FastAPI()
    app.include_router(skills_router)
    app.include_router(projects_router)
    client = TestClient(app)

    res = client.get("/api/skills")
    assert res.status_code == 200
    assert res.json()[0]["name"] == skills.LEARNINGS_SKILL_NAME

    # Unknown skills are rejected before anything is created or registered
    res = client.post(
        "/api/projects",
        json={"name": "skills-test", "path": str(user_skills / "p"), "skills": ["does-not-exist"]},
    )
    assert res.status_code == 400
    assert "does-not-exist" in res.json()["detail"]
    assert not (user_skills / "p").exists()
