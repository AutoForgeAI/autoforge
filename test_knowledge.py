"""
Tests for project knowledge files (.autoforge/knowledge/).

Covers the prompt section built by prompts.get_knowledge_prompt_section()
and the REST endpoints in server/routers/knowledge.py.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from prompts import get_knowledge_prompt_section, list_knowledge_files
from server.routers import knowledge as knowledge_router


class TestKnowledgePromptSection(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_knowledge_dir_returns_empty(self):
        assert list_knowledge_files(self.project_dir) == []
        assert get_knowledge_prompt_section(self.project_dir) == ""
        assert get_knowledge_prompt_section(None) == ""

    def test_lists_only_text_files_sorted(self):
        kdir = self.project_dir / ".autoforge" / "knowledge"
        kdir.mkdir(parents=True)
        (kdir / "research.md").write_text("# Research")
        (kdir / "Requirements.markdown").write_text("# Reqs")
        (kdir / "notes.txt").write_text("notes")
        (kdir / "image.png").write_bytes(b"\x89PNG")
        (kdir / "subdir.md").mkdir()

        names = [p.name for p in list_knowledge_files(self.project_dir)]
        assert names == ["notes.txt", "Requirements.markdown", "research.md"]

        section = get_knowledge_prompt_section(self.project_dir)
        assert "PROJECT KNOWLEDGE FILES" in section
        assert "`.autoforge/knowledge/research.md`" in section
        assert "`.autoforge/knowledge/notes.txt`" in section
        assert "image.png" not in section


class TestKnowledgeRouter(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project_dir = Path(self._tmp.name)
        self._patcher = patch.object(
            knowledge_router, "_get_project_path",
            lambda name: self.project_dir if name == "demo" else None,
        )
        self._patcher.start()
        app = FastAPI()
        app.include_router(knowledge_router.router)
        self.client = TestClient(app)
        self.base = "/api/projects/demo/knowledge"

    def tearDown(self):
        self._patcher.stop()
        self._tmp.cleanup()

    def test_upload_list_get_delete_roundtrip(self):
        assert self.client.get(self.base).json() == []

        resp = self.client.post(self.base, json={"filename": "PRD v2.md", "content": "# PRD\nDetails"})
        assert resp.status_code == 200, resp.text
        assert resp.json()["filename"] == "PRD v2.md"
        assert (self.project_dir / ".autoforge" / "knowledge" / "PRD v2.md").read_text() == "# PRD\nDetails"

        listing = self.client.get(self.base).json()
        assert [f["filename"] for f in listing] == ["PRD v2.md"]
        assert listing[0]["size"] == len("# PRD\nDetails")

        content = self.client.get(f"{self.base}/PRD%20v2.md").json()
        assert content == {"filename": "PRD v2.md", "content": "# PRD\nDetails"}

        # Re-upload overwrites
        self.client.post(self.base, json={"filename": "PRD v2.md", "content": "new"})
        assert self.client.get(f"{self.base}/PRD%20v2.md").json()["content"] == "new"

        assert self.client.delete(f"{self.base}/PRD%20v2.md").status_code == 200
        assert self.client.get(self.base).json() == []
        assert self.client.delete(f"{self.base}/PRD%20v2.md").status_code == 404

    def test_rejects_bad_filenames(self):
        for bad in ["../evil.md", "a/b.md", ".hidden.md", "script.py", "noext", "a..b.md"]:
            resp = self.client.post(self.base, json={"filename": bad, "content": "x"})
            assert resp.status_code == 400, bad
        assert not (self.project_dir / "evil.md").exists()

    def test_path_traversal_on_get_and_delete(self):
        (self.project_dir / "secret.md").write_text("secret")
        assert self.client.get(f"{self.base}/..%2Fsecret.md").status_code in (400, 404)
        assert self.client.delete(f"{self.base}/..%2Fsecret.md").status_code in (400, 404)
        assert (self.project_dir / "secret.md").exists()

    def test_rejects_oversized_file(self):
        big = "x" * (knowledge_router.MAX_KNOWLEDGE_FILE_SIZE + 1)
        resp = self.client.post(self.base, json={"filename": "big.md", "content": big})
        assert resp.status_code == 413

    def test_file_count_limit(self):
        with patch.object(knowledge_router, "MAX_KNOWLEDGE_FILES", 2):
            assert self.client.post(self.base, json={"filename": "a.md", "content": "a"}).status_code == 200
            assert self.client.post(self.base, json={"filename": "b.md", "content": "b"}).status_code == 200
            assert self.client.post(self.base, json={"filename": "c.md", "content": "c"}).status_code == 400
            # Overwriting an existing file is still allowed at the limit
            assert self.client.post(self.base, json={"filename": "a.md", "content": "a2"}).status_code == 200

    def test_unknown_project_404(self):
        assert self.client.get("/api/projects/other/knowledge").status_code == 404


if __name__ == "__main__":
    unittest.main()
