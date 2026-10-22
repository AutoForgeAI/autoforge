"""
Project Layout Tests
====================

Verifies that new projects keep AutoForge's files under ``.autoforge/`` and do
not get a root-level ``app_spec.txt`` copy, while legacy projects whose prompts
still read the spec from the project root keep working.
"""

from pathlib import Path

from prompts import (
    TEMPLATES_DIR,
    copy_spec_to_project,
    get_project_prompts_dir,
    prompts_need_root_spec,
    scaffold_project_prompts,
)

SPEC = "<project_specification>test</project_specification>\n"


def _scaffold(project_dir: Path) -> Path:
    prompts_dir = scaffold_project_prompts(project_dir)
    (prompts_dir / "app_spec.txt").write_text(SPEC, encoding="utf-8")
    return prompts_dir


def test_templates_read_spec_from_autoforge_dir():
    for name in ("initializer_prompt.template.md", "coding_prompt.template.md"):
        content = (TEMPLATES_DIR / name).read_text(encoding="utf-8")
        assert ".autoforge/prompts/app_spec.txt" in content, name


def test_new_project_gets_no_root_spec_copy(tmp_path: Path):
    prompts_dir = _scaffold(tmp_path)

    assert prompts_dir == tmp_path / ".autoforge" / "prompts"
    assert not prompts_need_root_spec(tmp_path)

    copy_spec_to_project(tmp_path)
    assert not (tmp_path / "app_spec.txt").exists()


def test_legacy_prompts_still_get_root_spec_copy(tmp_path: Path):
    prompts_dir = _scaffold(tmp_path)
    (prompts_dir / "coding_prompt.md").write_text(
        "## YOUR ROLE\n\n```bash\ncat app_spec.txt\n```\n", encoding="utf-8"
    )

    assert prompts_need_root_spec(tmp_path)

    copy_spec_to_project(tmp_path)
    root_spec = tmp_path / "app_spec.txt"
    assert root_spec.read_text(encoding="utf-8") == SPEC


def test_existing_root_spec_is_not_overwritten(tmp_path: Path):
    prompts_dir = _scaffold(tmp_path)
    (prompts_dir / "initializer_prompt.md").write_text(
        "Start by reading `app_spec.txt` in your working directory.", encoding="utf-8"
    )
    root_spec = tmp_path / "app_spec.txt"
    root_spec.write_text("custom", encoding="utf-8")

    copy_spec_to_project(tmp_path)
    assert root_spec.read_text(encoding="utf-8") == "custom"


def test_prompts_dir_resolves_to_autoforge(tmp_path: Path):
    _scaffold(tmp_path)
    assert get_project_prompts_dir(tmp_path) == tmp_path / ".autoforge" / "prompts"
