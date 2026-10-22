"""
Tests for importing an existing AutoForge project folder into the registry.

Covers is_existing_autoforge_project() in autoforge_paths.py and the
POST /api/projects/import endpoint in server/routers/projects.py.
"""

import asyncio
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi import HTTPException

import registry
from autoforge_paths import is_existing_autoforge_project
from server.routers.projects import import_project
from server.schemas import ProjectImport


def _make_features_db(path: Path) -> None:
    """Create a minimal features.db with one passing and one pending feature."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE features (id INTEGER PRIMARY KEY, passes BOOLEAN, in_progress BOOLEAN)"
    )
    conn.execute("INSERT INTO features (passes, in_progress) VALUES (1, 0), (0, 0)")
    conn.commit()
    conn.close()


class TestIsExistingAutoforgeProject(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_empty_folder_is_not_a_project(self):
        assert is_existing_autoforge_project(self.root) is False

    def test_missing_folder_is_not_a_project(self):
        assert is_existing_autoforge_project(self.root / "nope") is False

    def test_features_db_in_autoforge_dir(self):
        _make_features_db(self.root / ".autoforge" / "features.db")
        assert is_existing_autoforge_project(self.root) is True

    def test_spec_only_in_autoforge_prompts(self):
        prompts = self.root / ".autoforge" / "prompts"
        prompts.mkdir(parents=True)
        (prompts / "app_spec.txt").write_text("<project_specification/>")
        assert is_existing_autoforge_project(self.root) is True

    def test_legacy_root_level_layout(self):
        _make_features_db(self.root / "features.db")
        assert is_existing_autoforge_project(self.root) is True

    def test_legacy_autocoder_layout(self):
        _make_features_db(self.root / ".autocoder" / "features.db")
        assert is_existing_autoforge_project(self.root) is True


class TestImportProjectEndpoint(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

        # Isolate the registry in a temporary database
        self._registry_patch = mock.patch.object(
            registry, "get_registry_path", return_value=self.root / "registry.db"
        )
        self._registry_patch.start()
        registry._engine = None
        registry._SessionLocal = None

        # Temp dirs live under /tmp, which the filesystem blocklist rejects on Linux
        self._blocked_patch = mock.patch(
            "server.routers.filesystem.is_path_blocked", return_value=False
        )
        self._blocked_patch.start()

        self.project_dir = self.root / "my-app"
        _make_features_db(self.project_dir / ".autoforge" / "features.db")

    def tearDown(self):
        self._blocked_patch.stop()
        self._registry_patch.stop()
        if registry._engine is not None:
            registry._engine.dispose()
        registry._engine = None
        registry._SessionLocal = None
        self._tmp.cleanup()

    def _import(self, name: str, path: Path):
        return asyncio.run(import_project(ProjectImport(name=name, path=str(path))))

    def test_import_registers_existing_project_without_modifying_it(self):
        before = sorted(p.relative_to(self.project_dir) for p in self.project_dir.rglob("*"))

        result = self._import("my-app", self.project_dir)

        assert result.name == "my-app"
        assert result.stats.total == 2
        assert result.stats.passing == 1
        assert registry.get_project_path("my-app") == self.project_dir.resolve()
        after = sorted(p.relative_to(self.project_dir) for p in self.project_dir.rglob("*"))
        assert before == after

    def test_import_rejects_folder_without_autoforge_data(self):
        empty = self.root / "empty"
        empty.mkdir()
        with self.assertRaises(HTTPException) as ctx:
            self._import("empty", empty)
        assert ctx.exception.status_code == 400
        assert registry.get_project_path("empty") is None

    def test_import_rejects_missing_folder(self):
        with self.assertRaises(HTTPException) as ctx:
            self._import("ghost", self.root / "ghost")
        assert ctx.exception.status_code == 404

    def test_import_rejects_duplicate_name(self):
        self._import("my-app", self.project_dir)
        other = self.root / "other"
        _make_features_db(other / ".autoforge" / "features.db")
        with self.assertRaises(HTTPException) as ctx:
            self._import("my-app", other)
        assert ctx.exception.status_code == 409

    def test_import_rejects_already_registered_path(self):
        self._import("my-app", self.project_dir)
        with self.assertRaises(HTTPException) as ctx:
            self._import("renamed", self.project_dir)
        assert ctx.exception.status_code == 409

    def test_import_rejects_blocked_path(self):
        with mock.patch("server.routers.filesystem.is_path_blocked", return_value=True):
            with self.assertRaises(HTTPException) as ctx:
                self._import("my-app", self.project_dir)
        assert ctx.exception.status_code == 403


if __name__ == "__main__":
    unittest.main()
