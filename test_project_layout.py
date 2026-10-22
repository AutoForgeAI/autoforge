"""
Project Layout Tests
====================

Verify that AutoForge keeps its own files (spec, progress notes) under
``.autoforge/`` instead of the project root, and that older projects are
migrated without losing data.

Run with: python -m pytest test_project_layout.py
"""

from pathlib import Path

import prompts
from prompts import (
    CURRENT_MIGRATION_VERSION,
    _migrate_v1_to_v2,
    _set_migration_version,
    copy_spec_to_project,
    migrate_project_to_current,
    scaffold_project_prompts,
)

SPEC = "<project_specification>demo</project_specification>\n"

LEGACY_CODING_PROMPT = """\
cat app_spec.txt
tail -500 claude-progress.txt
Understanding the `app_spec.txt` is critical.
Update `claude-progress.txt` with notes.
"""


def _make_v1_project(tmp_path: Path, coding_prompt: str = LEGACY_CODING_PROMPT) -> Path:
    prompts_dir = tmp_path / ".autoforge" / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "app_spec.txt").write_text(SPEC, encoding="utf-8")
    (prompts_dir / "coding_prompt.md").write_text(coding_prompt, encoding="utf-8")
    _set_migration_version(tmp_path, 1)
    return tmp_path


def test_templates_do_not_reference_root_files():
    for name in ("coding_prompt", "initializer_prompt", "testing_prompt"):
        content = (prompts.TEMPLATES_DIR / f"{name}.template.md").read_text(encoding="utf-8")
        assert not prompts._references_root_file(content, "app_spec.txt"), name
        assert not prompts._references_root_file(content, "claude-progress.txt"), name


def test_new_project_does_not_get_root_spec_copy(tmp_path):
    scaffold_project_prompts(tmp_path)
    (tmp_path / ".autoforge" / "prompts" / "app_spec.txt").write_text(SPEC, encoding="utf-8")

    copy_spec_to_project(tmp_path)

    assert not (tmp_path / "app_spec.txt").exists()


def test_legacy_prompt_still_gets_root_spec_copy(tmp_path):
    _make_v1_project(tmp_path)

    copy_spec_to_project(tmp_path)

    assert (tmp_path / "app_spec.txt").read_text(encoding="utf-8") == SPEC


def test_migration_moves_files_and_rewrites_prompts(tmp_path):
    project = _make_v1_project(tmp_path)
    (project / "app_spec.txt").write_text(SPEC, encoding="utf-8")
    (project / "claude-progress.txt").write_text("session 1 notes\n", encoding="utf-8")

    migrated = migrate_project_to_current(project)

    assert migrated
    assert not (project / "app_spec.txt").exists()
    assert not (project / "claude-progress.txt").exists()
    assert (project / ".autoforge" / "claude-progress.txt").read_text(encoding="utf-8") == "session 1 notes\n"

    coding = (project / ".autoforge" / "prompts" / "coding_prompt.md").read_text(encoding="utf-8")
    assert "cat .autoforge/prompts/app_spec.txt" in coding
    assert "tail -500 .autoforge/claude-progress.txt" in coding
    assert "`.autoforge/prompts/app_spec.txt`" in coding
    assert not prompts._references_root_file(coding, "app_spec.txt")

    assert prompts._get_migration_version(project) == CURRENT_MIGRATION_VERSION
    # Idempotent
    assert migrate_project_to_current(project) == []


def test_migration_is_idempotent_on_rewritten_prompts(tmp_path):
    project = _make_v1_project(tmp_path)
    _migrate_v1_to_v2(project)
    first = (project / ".autoforge" / "prompts" / "coding_prompt.md").read_text(encoding="utf-8")

    _migrate_v1_to_v2(project)
    second = (project / ".autoforge" / "prompts" / "coding_prompt.md").read_text(encoding="utf-8")

    assert first == second
    assert ".autoforge/.autoforge" not in second
    assert "prompts/.autoforge" not in second


def test_migration_keeps_edited_root_spec(tmp_path):
    project = _make_v1_project(tmp_path)
    (project / "app_spec.txt").write_text("edited by hand\n", encoding="utf-8")

    _migrate_v1_to_v2(project)

    assert (project / "app_spec.txt").read_text(encoding="utf-8") == "edited by hand\n"


def test_migration_copies_root_only_spec_into_prompts(tmp_path):
    project = _make_v1_project(tmp_path)
    canonical = project / ".autoforge" / "prompts" / "app_spec.txt"
    canonical.unlink()
    (project / "app_spec.txt").write_text(SPEC, encoding="utf-8")

    _migrate_v1_to_v2(project)

    assert canonical.read_text(encoding="utf-8") == SPEC
    # Identical copy at the root is now redundant
    assert not (project / "app_spec.txt").exists()


def test_migration_does_not_overwrite_existing_progress_notes(tmp_path):
    project = _make_v1_project(tmp_path)
    (project / "claude-progress.txt").write_text("root notes\n", encoding="utf-8")
    (project / ".autoforge" / "claude-progress.txt").write_text("new notes\n", encoding="utf-8")

    _migrate_v1_to_v2(project)

    assert (project / "claude-progress.txt").read_text(encoding="utf-8") == "root notes\n"
    assert (project / ".autoforge" / "claude-progress.txt").read_text(encoding="utf-8") == "new notes\n"
