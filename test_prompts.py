"""
Prompt Tests
============

Tests for the scripted regression-test instructions injected into coding and
testing prompts (issue #157: replace repeated manual re-testing with scripts).

Run with:
    python -m pytest test_prompts.py -v
"""

from pathlib import Path

from prompts import (
    REGRESSION_SCRIPT_CODING_SECTION,
    REGRESSION_TESTS_DIR,
    _add_regression_script_section,
    get_batch_feature_prompt,
    get_coding_prompt,
    get_single_feature_prompt,
    get_testing_prompt,
)


def test_coding_prompt_includes_regression_script_step_before_step_6():
    prompt = get_coding_prompt()
    assert "STEP 5.8: SAVE A REGRESSION TEST SCRIPT" in prompt
    assert prompt.count("STEP 5.8:") == 1
    assert prompt.index("STEP 5.8:") < prompt.index("### STEP 6:")
    assert f"{REGRESSION_TESTS_DIR}/feature-<ID>.spec.ts" in prompt


def test_coding_prompt_yolo_mode_has_no_regression_script_step():
    prompt = get_coding_prompt(yolo_mode=True)
    assert "STEP 5.8:" not in prompt


def test_single_and_batch_prompts_include_regression_script_step():
    assert "STEP 5.8:" in get_single_feature_prompt(7)
    assert "STEP 5.8:" in get_batch_feature_prompt([1, 2])
    assert "STEP 5.8:" not in get_single_feature_prompt(7, yolo_mode=True)
    assert "STEP 5.8:" not in get_batch_feature_prompt([1, 2], yolo_mode=True)


def test_add_section_appends_when_custom_prompt_has_no_step_6():
    custom = "## My custom coding prompt\n\nDo the work."
    result = _add_regression_script_section(custom)
    assert result.startswith(custom)
    assert result.endswith(REGRESSION_SCRIPT_CODING_SECTION)


def test_testing_prompt_runs_scripts_first():
    prompt = get_testing_prompt(testing_feature_ids=[3, 5])
    assert prompt.startswith("## SCRIPTED REGRESSION TESTS (RUN THESE FIRST)")
    assert f"npx playwright test {REGRESSION_TESTS_DIR}/feature-<ID>.spec.ts" in prompt
    # The original testing workflow (manual fallback) is still present
    assert "## YOUR ROLE - TESTING AGENT" in prompt
    assert "3, 5" in prompt
    assert "{{TESTING_FEATURE_IDS}}" not in prompt


def test_testing_prompt_header_applies_to_single_and_unassigned_modes():
    assert get_testing_prompt(testing_feature_id=9).startswith("## SCRIPTED REGRESSION TESTS")
    assert get_testing_prompt().startswith("## SCRIPTED REGRESSION TESTS")


def test_project_specific_prompts_also_get_regression_instructions(tmp_path: Path):
    prompts_dir = tmp_path / ".autoforge" / "prompts"
    prompts_dir.mkdir(parents=True)
    (prompts_dir / "coding_prompt.md").write_text("custom coding\n\n### STEP 6: MARK\n", encoding="utf-8")
    (prompts_dir / "testing_prompt.md").write_text("custom testing {{TESTING_FEATURE_IDS}}", encoding="utf-8")

    coding = get_coding_prompt(tmp_path)
    assert coding.startswith("custom coding")
    assert coding.index("STEP 5.8:") < coding.index("### STEP 6: MARK")

    testing = get_testing_prompt(tmp_path, testing_feature_ids=[4])
    assert testing.startswith("## SCRIPTED REGRESSION TESTS")
    assert testing.endswith("custom testing 4")
