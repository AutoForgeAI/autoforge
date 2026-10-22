"""
Tests for importing (re-registering) existing AutoForge projects.

Covers is_autoforge_project() detection and the POST /api/projects/import
endpoint, using an isolated registry in a temporary home directory.
"""

import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import registry
from autoforge_paths import is_autoforge_project
from server.routers import projects

SPEC = "<project_specification>\n  <project_name>demo</project_name>\n</project_specification>\n"


def _make_features_db(db_path: Path, passing: int, total: int) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE features (id INTEGER PRIMARY KEY, priority INTEGER, category TEXT, "
        "name TEXT, description TEXT, steps TEXT, passes BOOLEAN, in_progress BOOLEAN, "
        "dependencies TEXT, needs_human_input BOOLEAN)"
    )
    for i in range(total):
        conn.execute(
            "INSERT INTO features (priority, category, name, description, steps, passes, "
            "in_progress, dependencies, needs_human_input) VALUES (?, 'c', ?, 'd', '[]', ?, 0, NULL, 0)",
            (i, f"feature {i}", 1 if i < passing else 0),
        )
    conn.commit()
    conn.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient with the registry pointed at a throwaway home directory."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(registry, "_engine", None)
    monkeypatch.setattr(registry, "_SessionLocal", None)

    app = FastAPI()
    app.include_router(projects.router)
    yield TestClient(app)

    if registry._engine is not None:
        registry._engine.dispose()


@pytest.fixture
def existing_project(tmp_path):
    """An existing project folder with a spec and 2/3 passing features."""
    project = tmp_path / "work" / "my app"
    _make_features_db(project / ".autoforge" / "features.db", passing=2, total=3)
    prompts = project / ".autoforge" / "prompts"
    prompts.mkdir(parents=True)
    (prompts / "app_spec.txt").write_text(SPEC, encoding="utf-8")
    return project


class TestIsAutoforgeProject:
    def test_empty_folder(self, tmp_path):
        assert is_autoforge_project(tmp_path) is False

    def test_current_layout_db(self, tmp_path):
        _make_features_db(tmp_path / ".autoforge" / "features.db", 0, 1)
        assert is_autoforge_project(tmp_path) is True

    def test_spec_only(self, tmp_path):
        (tmp_path / ".autoforge" / "prompts").mkdir(parents=True)
        (tmp_path / ".autoforge" / "prompts" / "app_spec.txt").write_text(SPEC)
        assert is_autoforge_project(tmp_path) is True

    def test_legacy_autocoder_layout(self, tmp_path):
        _make_features_db(tmp_path / ".autocoder" / "features.db", 0, 1)
        assert is_autoforge_project(tmp_path) is True

    def test_legacy_root_layout(self, tmp_path):
        _make_features_db(tmp_path / "features.db", 0, 1)
        assert is_autoforge_project(tmp_path) is True

    def test_bare_autoforge_dir_not_enough(self, tmp_path):
        (tmp_path / ".autoforge").mkdir()
        assert is_autoforge_project(tmp_path) is False


class TestImportEndpoint:
    def test_import_registers_and_keeps_progress(self, client, existing_project):
        spec_before = (existing_project / ".autoforge" / "prompts" / "app_spec.txt").read_text()

        res = client.post("/api/projects/import", json={"name": "my-app", "path": str(existing_project)})
        assert res.status_code == 200, res.text
        body = res.json()
        assert body["name"] == "my-app"
        assert body["has_spec"] is True
        assert body["stats"]["passing"] == 2
        assert body["stats"]["total"] == 3

        # Shows up in the project list
        names = [p["name"] for p in client.get("/api/projects").json()]
        assert "my-app" in names

        # Nothing was scaffolded or overwritten
        assert (existing_project / ".autoforge" / "prompts" / "app_spec.txt").read_text() == spec_before
        assert not (existing_project / ".autoforge" / "prompts" / "coding_prompt.md").exists()

    def test_import_legacy_root_layout_does_not_shadow_prompts(self, client, tmp_path):
        project = tmp_path / "legacy"
        _make_features_db(project / "features.db", passing=1, total=1)
        (project / "prompts").mkdir()
        (project / "prompts" / "app_spec.txt").write_text(SPEC)

        res = client.post("/api/projects/import", json={"name": "legacy", "path": str(project)})
        assert res.status_code == 200, res.text
        assert res.json()["has_spec"] is True
        assert res.json()["stats"]["total"] == 1
        # No new-layout prompts dir that would take precedence over prompts/
        assert not (project / ".autoforge" / "prompts").exists()

    def test_rejects_non_project_folder(self, client, tmp_path):
        folder = tmp_path / "plain"
        folder.mkdir()
        res = client.post("/api/projects/import", json={"name": "plain", "path": str(folder)})
        assert res.status_code == 400
        assert "does not look like an AutoForge project" in res.json()["detail"]

    def test_rejects_missing_folder(self, client, tmp_path):
        res = client.post("/api/projects/import", json={"name": "gone", "path": str(tmp_path / "nope")})
        assert res.status_code == 400
        assert "does not exist" in res.json()["detail"]
        assert not (tmp_path / "nope").exists()

    def test_rejects_duplicate_name(self, client, existing_project, tmp_path):
        assert client.post(
            "/api/projects/import", json={"name": "my-app", "path": str(existing_project)}
        ).status_code == 200

        other = tmp_path / "other"
        _make_features_db(other / ".autoforge" / "features.db", 0, 1)
        res = client.post("/api/projects/import", json={"name": "my-app", "path": str(other)})
        assert res.status_code == 409

    def test_rejects_already_registered_path(self, client, existing_project):
        assert client.post(
            "/api/projects/import", json={"name": "my-app", "path": str(existing_project)}
        ).status_code == 200
        res = client.post("/api/projects/import", json={"name": "again", "path": str(existing_project)})
        assert res.status_code == 409
        assert "already registered as project 'my-app'" in res.json()["detail"]

    def test_rejects_invalid_name(self, client, existing_project):
        res = client.post("/api/projects/import", json={"name": "../evil", "path": str(existing_project)})
        assert res.status_code == 422
