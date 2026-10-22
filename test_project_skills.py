"""
Project Skills Tests
====================

Tests for the skill library, per-project skill installation, and the
skill-learning prompt section.

Run with: python -m pytest test_project_skills.py -v
"""

from pathlib import Path

import pytest

import project_skills
from project_skills import (
    LEARNINGS_SKILL_NAME,
    has_learnings_skill,
    install_skills,
    is_valid_skill_name,
    list_library_skills,
    list_project_skills,
    parse_skill_metadata,
    remove_skill,
)


def _make_skill(root: Path, name: str, description: str = "A test skill") -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )
    return skill_dir


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Point the user skill libraries at a temp home directory."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(project_skills.Path, "home", classmethod(lambda cls: home))
    return home


@pytest.fixture
def project_dir(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    return project


class TestSkillNames:
    @pytest.mark.parametrize("name", ["frontend-design", "my_skill", "a", "skill.v2"])
    def test_valid(self, name):
        assert is_valid_skill_name(name)

    @pytest.mark.parametrize("name", ["", "..", "../etc", "a/b", "a\\b", ".hidden", "-x", "a..b", "x" * 65])
    def test_invalid(self, name):
        assert not is_valid_skill_name(name)


class TestParseMetadata:
    def test_parses_frontmatter(self, tmp_path):
        skill = _make_skill(tmp_path, "demo", "Does demo things")
        assert parse_skill_metadata(skill / "SKILL.md") == {"name": "demo", "description": "Does demo things"}

    def test_missing_frontmatter(self, tmp_path):
        md = tmp_path / "SKILL.md"
        md.write_text("# no frontmatter\n", encoding="utf-8")
        assert parse_skill_metadata(md) == {}

    def test_invalid_yaml(self, tmp_path):
        md = tmp_path / "SKILL.md"
        md.write_text("---\nname: [unclosed\n---\n", encoding="utf-8")
        assert parse_skill_metadata(md) == {}


class TestLibrary:
    def test_bundled_skills_listed(self, fake_home):
        names = {s["name"] for s in list_library_skills()}
        assert LEARNINGS_SKILL_NAME in names
        assert "playwright-cli" in names
        assert "frontend-design" in names
        # AutoForge-internal skill is not offered to generated projects
        assert "gsd-to-autoforge-spec" not in names

    def test_flags(self, fake_home):
        by_name = {s["name"]: s for s in list_library_skills()}
        assert by_name["playwright-cli"]["required"] is True
        assert by_name[LEARNINGS_SKILL_NAME]["recommended"] is True
        assert by_name["frontend-design"]["source"] == "bundled"

    def test_user_skills_listed(self, fake_home):
        _make_skill(fake_home / ".autoforge" / "skills", "my-autoforge-skill")
        _make_skill(fake_home / ".claude" / "skills", "my-claude-skill")
        by_name = {s["name"]: s for s in list_library_skills()}
        assert by_name["my-autoforge-skill"]["source"] == "user"
        assert by_name["my-claude-skill"]["source"] == "claude"

    def test_bundled_takes_precedence(self, fake_home):
        _make_skill(fake_home / ".claude" / "skills", "frontend-design", "user copy")
        matches = [s for s in list_library_skills() if s["name"] == "frontend-design"]
        assert len(matches) == 1
        assert matches[0]["source"] == "bundled"

    def test_dirs_without_skill_md_ignored(self, fake_home):
        (fake_home / ".autoforge" / "skills" / "not-a-skill").mkdir(parents=True)
        assert "not-a-skill" not in {s["name"] for s in list_library_skills()}


class TestInstallRemove:
    def test_install_and_list(self, fake_home, project_dir):
        installed, skipped = install_skills(project_dir, ["frontend-design", "unknown-skill"])
        assert installed == ["frontend-design"]
        assert skipped == ["unknown-skill"]
        assert (project_dir / ".claude" / "skills" / "frontend-design" / "SKILL.md").is_file()
        assert [s["name"] for s in list_project_skills(project_dir)] == ["frontend-design"]

    def test_install_preserves_existing(self, fake_home, project_dir):
        install_skills(project_dir, [LEARNINGS_SKILL_NAME])
        skill_md = project_dir / ".claude" / "skills" / LEARNINGS_SKILL_NAME / "SKILL.md"
        skill_md.write_text("---\nname: project-learnings\n---\nlearned stuff\n", encoding="utf-8")
        installed, skipped = install_skills(project_dir, [LEARNINGS_SKILL_NAME])
        assert installed == []
        assert skipped == [LEARNINGS_SKILL_NAME]
        assert "learned stuff" in skill_md.read_text(encoding="utf-8")

    def test_install_rejects_traversal(self, fake_home, project_dir):
        with pytest.raises(ValueError):
            install_skills(project_dir, ["../../etc"])

    def test_install_skips_symlinks(self, fake_home, project_dir, tmp_path):
        secret = tmp_path / "secret.txt"
        secret.write_text("top secret", encoding="utf-8")
        skill = _make_skill(fake_home / ".autoforge" / "skills", "linky")
        try:
            (skill / "leak.txt").symlink_to(secret)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks not supported")
        install_skills(project_dir, ["linky"])
        dest = project_dir / ".claude" / "skills" / "linky"
        assert (dest / "SKILL.md").is_file()
        assert not (dest / "leak.txt").exists()

    def test_remove(self, fake_home, project_dir):
        install_skills(project_dir, ["frontend-design"])
        assert remove_skill(project_dir, "frontend-design") is True
        assert not (project_dir / ".claude" / "skills" / "frontend-design").exists()
        assert remove_skill(project_dir, "frontend-design") is False

    def test_remove_required_refused(self, project_dir):
        with pytest.raises(ValueError):
            remove_skill(project_dir, "playwright-cli")

    def test_remove_rejects_traversal(self, project_dir):
        with pytest.raises(ValueError):
            remove_skill(project_dir, "..")


class TestLearningsPrompt:
    def test_section_only_when_skill_installed(self, fake_home, project_dir):
        from prompts import get_coding_prompt, get_learnings_section, get_single_feature_prompt

        assert not has_learnings_skill(project_dir)
        assert get_learnings_section(project_dir) == ""
        assert "SKILL LEARNING" not in get_coding_prompt(project_dir)

        install_skills(project_dir, [LEARNINGS_SKILL_NAME])
        assert has_learnings_skill(project_dir)
        assert "SKILL LEARNING" in get_coding_prompt(project_dir)
        assert "SKILL LEARNING" in get_coding_prompt(project_dir, yolo_mode=True)
        assert "SKILL LEARNING" in get_single_feature_prompt(1, project_dir)

    def test_no_project_dir(self):
        from prompts import get_learnings_section

        assert get_learnings_section(None) == ""
