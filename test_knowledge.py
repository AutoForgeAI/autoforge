"""
Tests for project knowledge documents (issue #22).

Covers the prompt pointer added for every agent session and the REST API
used by the UI to upload/list/read/delete documents.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from prompts import get_knowledge_files, with_project_knowledge
from server.routers import knowledge as knowledge_router

# ---------------------------------------------------------------------------
# Prompt integration
# ---------------------------------------------------------------------------

def test_prompt_unchanged_without_knowledge(tmp_path: Path) -> None:
    assert with_project_knowledge("BASE", tmp_path) == "BASE"
    assert with_project_knowledge("BASE", None) == "BASE"


def test_prompt_lists_knowledge_files(tmp_path: Path) -> None:
    kdir = tmp_path / ".autoforge" / "knowledge"
    kdir.mkdir(parents=True)
    (kdir / "requirements.md").write_text("# Reqs", encoding="utf-8")
    (kdir / "Research.txt").write_text("notes", encoding="utf-8")
    (kdir / "image.png").write_bytes(b"\x89PNG")

    names = [p.name for p in get_knowledge_files(tmp_path)]
    assert names == ["requirements.md", "Research.txt"]

    prompt = with_project_knowledge("BASE", tmp_path)
    assert prompt.startswith("## PROJECT KNOWLEDGE")
    assert "`.autoforge/knowledge/requirements.md`" in prompt
    assert "`.autoforge/knowledge/Research.txt`" in prompt
    assert "image.png" not in prompt
    assert prompt.endswith("BASE")


# ---------------------------------------------------------------------------
# REST API
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(
        knowledge_router, "_get_project_path",
        lambda name: tmp_path if name == "demo" else None,
    )
    app = FastAPI()
    app.include_router(knowledge_router.router)
    return TestClient(app)


def test_upload_list_read_delete(client: TestClient, tmp_path: Path) -> None:
    assert client.get("/api/projects/demo/knowledge").json() == {"files": []}

    res = client.post("/api/projects/demo/knowledge", json={"filename": "prd.md", "content": "# PRD\nDetails"})
    assert res.status_code == 201
    assert res.json()["name"] == "prd.md"
    assert (tmp_path / ".autoforge" / "knowledge" / "prd.md").read_text(encoding="utf-8") == "# PRD\nDetails"

    files = client.get("/api/projects/demo/knowledge").json()["files"]
    assert [f["name"] for f in files] == ["prd.md"]

    res = client.get("/api/projects/demo/knowledge/prd.md")
    assert res.json() == {"name": "prd.md", "content": "# PRD\nDetails"}

    # Re-uploading overwrites
    client.post("/api/projects/demo/knowledge", json={"filename": "prd.md", "content": "v2"})
    assert client.get("/api/projects/demo/knowledge/prd.md").json()["content"] == "v2"

    assert client.delete("/api/projects/demo/knowledge/prd.md").status_code == 204
    assert client.get("/api/projects/demo/knowledge/prd.md").status_code == 404


@pytest.mark.parametrize("filename", [
    "../evil.md",
    ".hidden.md",
    "notes.exe",
    "sub/dir.md",
    "a..md",
])
def test_rejects_bad_filenames(client: TestClient, filename: str) -> None:
    res = client.post("/api/projects/demo/knowledge", json={"filename": filename, "content": "x"})
    assert res.status_code == 400


def test_rejects_oversized_file(client: TestClient) -> None:
    content = "x" * (knowledge_router.MAX_KNOWLEDGE_FILE_SIZE + 1)
    res = client.post("/api/projects/demo/knowledge", json={"filename": "big.md", "content": content})
    assert res.status_code == 413


def test_unknown_project(client: TestClient) -> None:
    assert client.get("/api/projects/other/knowledge").status_code == 404
