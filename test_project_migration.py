"""
Project Migration Tests
=======================

Tests for migrating legacy (AutoCoder-era) projects to the ``.autoforge/``
layout, including scaffolding of ``.autoforge/allowed_commands.yaml``.

Run with: python -m pytest test_project_migration.py -v
"""

import tempfile
import unittest
from pathlib import Path

from autoforge_paths import migrate_project_layout
from prompts import (
    CURRENT_MIGRATION_VERSION,
    _get_migration_version,
    _set_migration_version,
    migrate_project_to_current,
    scaffold_project_prompts,
)


class TestAutocoderMigration(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _make_autocoder_project(self) -> None:
        prompts = self.project / ".autocoder" / "prompts"
        prompts.mkdir(parents=True)
        (prompts / "app_spec.txt").write_text("<project_specification>x</project_specification>")
        (prompts / "coding_prompt.md").write_text("custom coding prompt")
        (self.project / ".autocoder" / ".progress_cache").write_text("{}")

    def test_renames_autocoder_dir(self):
        self._make_autocoder_project()
        migrated = migrate_project_layout(self.project)
        self.assertIn(".autocoder/ -> .autoforge/", migrated)
        self.assertFalse((self.project / ".autocoder").exists())
        self.assertTrue((self.project / ".autoforge" / "prompts" / "app_spec.txt").exists())

    def test_merges_into_existing_autoforge_dir(self):
        self._make_autocoder_project()
        (self.project / ".autoforge").mkdir()
        (self.project / ".autoforge" / ".gitignore").write_text("x")

        migrate_project_layout(self.project)

        self.assertFalse((self.project / ".autocoder").exists())
        self.assertEqual(
            (self.project / ".autoforge" / "prompts" / "coding_prompt.md").read_text(),
            "custom coding prompt",
        )
        self.assertTrue((self.project / ".autoforge" / ".progress_cache").exists())

    def test_merge_keeps_existing_autoforge_entries(self):
        self._make_autocoder_project()
        new_prompts = self.project / ".autoforge" / "prompts"
        new_prompts.mkdir(parents=True)
        (new_prompts / "coding_prompt.md").write_text("new")

        migrate_project_layout(self.project)

        self.assertEqual((new_prompts / "coding_prompt.md").read_text(), "new")
        # Conflicting entry stays behind, so .autocoder/ is not removed
        self.assertTrue((self.project / ".autocoder" / "prompts").exists())
        self.assertTrue((self.project / ".autoforge" / ".progress_cache").exists())

    def test_version_migration_creates_allowed_commands(self):
        self._make_autocoder_project()
        migrate_project_layout(self.project)
        _set_migration_version(self.project, 1)

        migrated = migrate_project_to_current(self.project)

        self.assertIn("Created .autoforge/allowed_commands.yaml", migrated)
        self.assertTrue((self.project / ".autoforge" / "allowed_commands.yaml").exists())
        self.assertEqual(_get_migration_version(self.project), CURRENT_MIGRATION_VERSION)

    def test_version_migration_keeps_existing_allowed_commands(self):
        autoforge = self.project / ".autoforge"
        autoforge.mkdir()
        (autoforge / "allowed_commands.yaml").write_text("version: 1\ncommands: []\n")
        _set_migration_version(self.project, 1)

        migrate_project_to_current(self.project)

        self.assertEqual(
            (autoforge / "allowed_commands.yaml").read_text(), "version: 1\ncommands: []\n"
        )

    def test_scaffold_new_project(self):
        scaffold_project_prompts(self.project)
        self.assertTrue((self.project / ".autoforge" / "allowed_commands.yaml").exists())
        self.assertEqual(_get_migration_version(self.project), CURRENT_MIGRATION_VERSION)

    def test_scaffold_existing_project_does_not_skip_migrations(self):
        self._make_autocoder_project()
        migrate_project_layout(self.project)

        scaffold_project_prompts(self.project)

        self.assertTrue((self.project / ".autoforge" / "allowed_commands.yaml").exists())
        # Existing prompts were kept, so pending prompt migrations must still run
        self.assertEqual(_get_migration_version(self.project), 0)
        self.assertEqual(
            (self.project / ".autoforge" / "prompts" / "coding_prompt.md").read_text(),
            "custom coding prompt",
        )


if __name__ == "__main__":
    unittest.main()
