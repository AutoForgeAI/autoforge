"""
Unit tests for onboarding an existing codebase (issue #134).

Covers:
- The PreToolUse hook that limits onboarding writes to app_spec.txt
- Parsing feature_create_bulk results for the created-features counter
- feature_create_bulk's optional "passes" flag for existing functionality
"""

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

import mcp_server.feature_mcp as feature_mcp
from api.database import Feature, create_database
from server.services.expand_chat_session import (
    _parse_created_count,
    make_spec_only_write_hook,
)


def _run_hook(hook, tool_name: str, tool_input: dict) -> dict:
    return asyncio.run(hook({"tool_name": tool_name, "tool_input": tool_input}))


class TestSpecOnlyWriteHook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name)
        self.spec = self.project / ".autoforge" / "prompts" / "app_spec.txt"
        self.spec.parent.mkdir(parents=True)
        self.hook = make_spec_only_write_hook(self.spec)

    def tearDown(self):
        self.tmp.cleanup()

    def test_allows_writing_spec(self):
        assert _run_hook(self.hook, "Write", {"file_path": str(self.spec)}) == {}
        assert _run_hook(self.hook, "Edit", {"file_path": str(self.spec)}) == {}

    def test_blocks_source_files(self):
        result = _run_hook(self.hook, "Write", {"file_path": str(self.project / "src" / "app.ts")})
        assert result["decision"] == "block"
        result = _run_hook(self.hook, "Edit", {"file_path": str(self.project / "README.md")})
        assert result["decision"] == "block"

    def test_blocks_traversal_and_missing_path(self):
        sneaky = self.spec.parent / ".." / ".." / "app_spec.txt"
        assert _run_hook(self.hook, "Write", {"file_path": str(sneaky)})["decision"] == "block"
        assert _run_hook(self.hook, "Write", {})["decision"] == "block"
        assert _run_hook(self.hook, "NotebookEdit", {"notebook_path": "x.ipynb"})["decision"] == "block"

    def test_ignores_other_tools(self):
        assert _run_hook(self.hook, "Read", {"file_path": str(self.project / "src" / "app.ts")}) == {}


class TestParseCreatedCount(unittest.TestCase):
    def test_parses_text_blocks_and_strings(self):
        assert _parse_created_count([{"type": "text", "text": '{"created": 4, "with_dependencies": 0}'}]) == 4
        assert _parse_created_count('{"created": 2}') == 2
        wrapped = json.dumps({"result": json.dumps({"created": 10, "with_dependencies": 9})})
        assert _parse_created_count([{"type": "text", "text": wrapped}]) == 10

    def test_handles_errors_and_garbage(self):
        assert _parse_created_count('{"error": "boom"}') == 0
        assert _parse_created_count("not json") == 0
        assert _parse_created_count(None) == 0


class TestBulkCreatePasses(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine, self.session_maker = create_database(Path(self.tmp.name))
        self._orig = feature_mcp._session_maker
        feature_mcp._session_maker = self.session_maker

    def tearDown(self):
        feature_mcp._session_maker = self._orig
        self.engine.dispose()
        self.tmp.cleanup()

    def _feature(self, name: str, **extra) -> dict:
        return {"category": "functional", "name": name, "description": "d", "steps": ["s"], **extra}

    def test_passes_flag_marks_existing_features(self):
        result = json.loads(feature_mcp.feature_create_bulk([
            self._feature("existing", passes=True),
            self._feature("new"),
        ]))
        assert result["created"] == 2

        session = self.session_maker()
        try:
            by_name = {f.name: f.passes for f in session.query(Feature).all()}
        finally:
            session.close()
        assert by_name == {"existing": True, "new": False}

    def test_rejects_non_boolean_passes(self):
        result = json.loads(feature_mcp.feature_create_bulk([self._feature("bad", passes="yes")]))
        assert "error" in result


if __name__ == "__main__":
    unittest.main()
