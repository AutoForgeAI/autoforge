"""
Prompt Tests
============

Tests for testing-agent prompt content and the v1 -> v2 prompt migration
that adds command-line verification for non-web projects (issue #136).

Run with: python -m pytest test_prompts.py -v
"""

import tempfile
import unittest
from pathlib import Path

import prompts
from prompts import (
    _CLI_TESTING_STEP2,
    CURRENT_MIGRATION_VERSION,
    _migrate_testing_prompt_to_v2,
    get_testing_prompt,
    migrate_project_to_current,
)

# Minimal reproduction of a project testing_prompt.md scaffolded from the v1 template
V1_TESTING_PROMPT = (
    "## YOUR ROLE - TESTING AGENT\n\n"
    "### Workflow for EACH feature:\n"
    "1. Call `feature_get_by_id` with the feature ID\n"
    "2. Read the feature's verification steps\n"
    "3. Test the feature in the browser\n"
    "4. Call `feature_mark_passing` or `feature_mark_failing`\n\n"
    "---\n\n"
    + _CLI_TESTING_STEP2
    + "### STEP 3: HANDLE RESULTS\n\n"
    "**Quality Bar:**\n- Zero console errors\n- All verification steps pass\n"
    "- Visual appearance correct\n- API calls succeed\n\n"
    "**If you find a regression:**\n"
    "3. Verify the fix with browser automation\n"
)


class TestTestingPromptTemplate(unittest.TestCase):
    def test_template_covers_browser_and_cli_verification(self):
        prompt = get_testing_prompt(testing_feature_ids=[1, 2])
        self.assertIn("1, 2", prompt)
        self.assertIn("#### 2A: Browser Automation", prompt)
        self.assertIn("#### 2B: Command-Line Verification", prompt)
        # Key steps requested in issue #136
        self.assertIn("Plan the success criteria BEFORE running anything", prompt)
        self.assertIn("simulated user input", prompt)
        self.assertIn("exit code", prompt)
        self.assertIn("bash tests/feature_<id>_test.sh", prompt)

    def test_template_step2_is_bounded_by_step3(self):
        section = prompts._get_template_section(
            "testing_prompt", r"### STEP 2: VERIFY THE FEATURE", r"### STEP 3:"
        )
        self.assertIsNotNone(section)
        assert section is not None
        self.assertIn("#### 2B:", section)
        self.assertNotIn("### STEP 3:", section)


class TestTestingPromptMigrationV2(unittest.TestCase):
    def test_migrates_unmodified_v1_prompt(self):
        updated = _migrate_testing_prompt_to_v2(V1_TESTING_PROMPT)
        self.assertNotIn(_CLI_TESTING_STEP2, updated)
        self.assertIn("#### 2B: Command-Line Verification", updated)
        self.assertIn("### STEP 3: HANDLE RESULTS", updated)
        self.assertNotIn("3. Test the feature in the browser\n", updated)
        self.assertIn("CLI / non-UI: expected exit codes", updated)
        self.assertIn("or your scenario script (CLI / non-UI)", updated)

    def test_migration_is_idempotent(self):
        once = _migrate_testing_prompt_to_v2(V1_TESTING_PROMPT)
        self.assertEqual(once, _migrate_testing_prompt_to_v2(once))

    def test_current_template_is_unchanged_by_migration(self):
        template = (prompts.TEMPLATES_DIR / "testing_prompt.template.md").read_text(encoding="utf-8")
        self.assertEqual(template, _migrate_testing_prompt_to_v2(template))

    def test_customized_step2_is_preserved(self):
        custom = V1_TESTING_PROMPT.replace(
            "**CRITICAL:** You MUST verify the feature through the actual UI using browser automation.",
            "**CRITICAL:** Run `make e2e` to verify.",
        )
        updated = _migrate_testing_prompt_to_v2(custom)
        self.assertIn("Run `make e2e` to verify.", updated)
        self.assertNotIn("#### 2B:", updated)

    def test_migrate_project_to_current_updates_testing_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            prompts_dir = project_dir / ".autoforge" / "prompts"
            prompts_dir.mkdir(parents=True)
            (project_dir / ".autoforge" / ".migration_version").write_text("1")
            testing_prompt = prompts_dir / "testing_prompt.md"
            testing_prompt.write_text(V1_TESTING_PROMPT, encoding="utf-8")

            migrated = migrate_project_to_current(project_dir)

            self.assertEqual(len(migrated), 1)
            self.assertIn("#### 2B:", testing_prompt.read_text(encoding="utf-8"))
            version = (project_dir / ".autoforge" / ".migration_version").read_text()
            self.assertEqual(version, str(CURRENT_MIGRATION_VERSION))
            # Second run is a no-op
            self.assertEqual(migrate_project_to_current(project_dir), [])


if __name__ == "__main__":
    unittest.main()
