#!/usr/bin/env python3
"""
Client Utility Tests
====================

Tests for the client module utility functions.
Run with: python test_client.py
"""

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

from client import (
    EXTRA_READ_PATHS_BLOCKLIST,
    EXTRA_READ_PATHS_VAR,
    CliStderrFilter,
    convert_model_for_vertex,
    get_extra_read_paths,
)


class TestConvertModelForVertex(unittest.TestCase):
    """Tests for convert_model_for_vertex function."""

    def setUp(self):
        """Save original env state."""
        self._orig_vertex = os.environ.get("CLAUDE_CODE_USE_VERTEX")

    def tearDown(self):
        """Restore original env state."""
        if self._orig_vertex is None:
            os.environ.pop("CLAUDE_CODE_USE_VERTEX", None)
        else:
            os.environ["CLAUDE_CODE_USE_VERTEX"] = self._orig_vertex

    # --- Vertex AI disabled (default) ---

    def test_returns_model_unchanged_when_vertex_disabled(self):
        os.environ.pop("CLAUDE_CODE_USE_VERTEX", None)
        self.assertEqual(
            convert_model_for_vertex("claude-opus-4-6"),
            "claude-opus-4-6",
        )

    def test_returns_model_unchanged_when_vertex_set_to_zero(self):
        os.environ["CLAUDE_CODE_USE_VERTEX"] = "0"
        self.assertEqual(
            convert_model_for_vertex("claude-opus-4-6"),
            "claude-opus-4-6",
        )

    def test_returns_model_unchanged_when_vertex_set_to_empty(self):
        os.environ["CLAUDE_CODE_USE_VERTEX"] = ""
        self.assertEqual(
            convert_model_for_vertex("claude-sonnet-4-5-20250929"),
            "claude-sonnet-4-5-20250929",
        )

    # --- Vertex AI enabled: standard conversions ---

    def test_converts_legacy_opus_model(self):
        os.environ["CLAUDE_CODE_USE_VERTEX"] = "1"
        self.assertEqual(
            convert_model_for_vertex("claude-opus-4-5-20251101"),
            "claude-opus-4-5@20251101",
        )

    def test_opus_4_6_passthrough_on_vertex(self):
        os.environ["CLAUDE_CODE_USE_VERTEX"] = "1"
        self.assertEqual(
            convert_model_for_vertex("claude-opus-4-6"),
            "claude-opus-4-6",
        )

    def test_converts_sonnet_model(self):
        os.environ["CLAUDE_CODE_USE_VERTEX"] = "1"
        self.assertEqual(
            convert_model_for_vertex("claude-sonnet-4-5-20250929"),
            "claude-sonnet-4-5@20250929",
        )

    def test_converts_haiku_model(self):
        os.environ["CLAUDE_CODE_USE_VERTEX"] = "1"
        self.assertEqual(
            convert_model_for_vertex("claude-3-5-haiku-20241022"),
            "claude-3-5-haiku@20241022",
        )

    # --- Vertex AI enabled: already converted or non-matching ---

    def test_already_vertex_format_unchanged(self):
        os.environ["CLAUDE_CODE_USE_VERTEX"] = "1"
        self.assertEqual(
            convert_model_for_vertex("claude-sonnet-4-5@20250929"),
            "claude-sonnet-4-5@20250929",
        )

    def test_non_claude_model_unchanged(self):
        os.environ["CLAUDE_CODE_USE_VERTEX"] = "1"
        self.assertEqual(
            convert_model_for_vertex("gpt-4o"),
            "gpt-4o",
        )

    def test_model_without_date_suffix_unchanged(self):
        os.environ["CLAUDE_CODE_USE_VERTEX"] = "1"
        self.assertEqual(
            convert_model_for_vertex("claude-opus-4-6"),
            "claude-opus-4-6",
        )

    def test_empty_string_unchanged(self):
        os.environ["CLAUDE_CODE_USE_VERTEX"] = "1"
        self.assertEqual(convert_model_for_vertex(""), "")


class TestCliStderrFilter(unittest.TestCase):
    """Tests for the CLI stderr filter that hides benign hook AbortErrors (#38)."""

    def _run(self, lines):
        out = io.StringIO()
        f = CliStderrFilter(stream=out)
        for line in lines:
            f(line)
        return out.getvalue().splitlines()

    def test_suppresses_hook_abort_error_and_stack(self):
        lines = [
            "Error in hook callback hook_0: VJ [AbortError]",
            "    at AbortSignal.Y (file:///x/cli.js:4930:315)",
            "    at [nodejs.internal.kHybridDispatch] (node:internal/event_target:845:20)",
            "    at runAbort (node:internal/abort_controller:488:10)",
        ]
        self.assertEqual(self._run(lines), [])

    def test_suppresses_abort_error_message_variant(self):
        lines = ["Error in hook callback hook_3: AbortError: The operation was aborted"]
        self.assertEqual(self._run(lines), [])

    def test_forwards_lines_after_abort_trace(self):
        lines = [
            "Error in hook callback hook_0: VJ [AbortError]",
            "    at AbortSignal.Y (file:///x/cli.js:4930:315)",
            "Some real error",
            "    at foo (bar.js:1:1)",
        ]
        self.assertEqual(self._run(lines), ["Some real error", "    at foo (bar.js:1:1)"])

    def test_forwards_other_hook_errors(self):
        lines = ["Error in hook callback hook_0: Error: boom", "    at x (y.js:1:1)"]
        self.assertEqual(self._run(lines), lines)

    # The SDK delivers raw pipe chunks (rstripped), not single lines.

    def test_chunk_with_real_error_after_abort_trace(self):
        chunk = (
            "Error in hook callback hook_0: VJ [AbortError]\n"
            "    at AbortSignal.Y (file:///x/cli.js:4930:315)\n"
            "    at runAbort (node:internal/abort_controller:488:10)\n"
            "Some real error\n"
            "    at foo (bar.js:1:1)"
        )
        self.assertEqual(self._run([chunk]), ["Some real error", "    at foo (bar.js:1:1)"])

    def test_chunk_with_real_error_before_abort_trace(self):
        chunk = (
            "Real problem: ENOSPC\n"
            "Error in hook callback hook_1: VJ [AbortError]\n"
            "    at AbortSignal.Y (file:///x/cli.js:4930:315)"
        )
        self.assertEqual(self._run([chunk]), ["Real problem: ENOSPC"])

    def test_chunk_with_only_abort_trace_is_suppressed(self):
        chunk = (
            "Error in hook callback hook_0: VJ [AbortError]\n"
            "    at AbortSignal.Y (file:///x/cli.js:4930:315)\n"
            "    at [nodejs.internal.kHybridDispatch] (node:internal/event_target:845:20)\n"
            "    at runAbort (node:internal/abort_controller:488:10)"
        )
        self.assertEqual(self._run([chunk]), [])

    def test_abort_trace_frames_continue_in_next_chunk(self):
        chunks = [
            "Error in hook callback hook_0: VJ [AbortError]\n    at AbortSignal.Y (file:///x/cli.js:4930:315)",
            "    at runAbort (node:internal/abort_controller:488:10)\nReal problem: ENOSPC",
        ]
        self.assertEqual(self._run(chunks), ["Real problem: ENOSPC"])


class TestExtraReadPathsBlocklist(unittest.TestCase):
    """Tests for EXTRA_READ_PATHS sensitive directory blocking in get_extra_read_paths()."""

    def setUp(self):
        """Save original environment and home directory state."""
        self._orig_extra_read = os.environ.get(EXTRA_READ_PATHS_VAR)
        self._orig_home = os.environ.get("HOME")
        self._orig_userprofile = os.environ.get("USERPROFILE")
        self._orig_homedrive = os.environ.get("HOMEDRIVE")
        self._orig_homepath = os.environ.get("HOMEPATH")

    def tearDown(self):
        """Restore original environment state."""
        restore_map = {
            EXTRA_READ_PATHS_VAR: self._orig_extra_read,
            "HOME": self._orig_home,
            "USERPROFILE": self._orig_userprofile,
            "HOMEDRIVE": self._orig_homedrive,
            "HOMEPATH": self._orig_homepath,
        }
        for key, value in restore_map.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def _set_home(self, home_path: str):
        """Set the home directory for both Unix and Windows."""
        os.environ["HOME"] = home_path
        if sys.platform == "win32":
            os.environ["USERPROFILE"] = home_path
            drive, path = os.path.splitdrive(home_path)
            if drive:
                os.environ["HOMEDRIVE"] = drive
                os.environ["HOMEPATH"] = path

    def test_sensitive_directory_is_blocked(self):
        """Path that IS a sensitive directory (e.g., ~/.ssh) should be blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._set_home(tmpdir)
            # Create the sensitive directory so it exists
            ssh_dir = Path(tmpdir) / ".ssh"
            ssh_dir.mkdir()

            os.environ[EXTRA_READ_PATHS_VAR] = str(ssh_dir)
            result = get_extra_read_paths()
            self.assertEqual(result, [], "Path that IS ~/.ssh should be blocked")

    def test_path_inside_sensitive_directory_is_blocked(self):
        """Path INSIDE a sensitive directory (e.g., ~/.ssh/keys) should be blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._set_home(tmpdir)
            ssh_dir = Path(tmpdir) / ".ssh"
            keys_dir = ssh_dir / "keys"
            keys_dir.mkdir(parents=True)

            os.environ[EXTRA_READ_PATHS_VAR] = str(keys_dir)
            result = get_extra_read_paths()
            self.assertEqual(result, [], "Path inside ~/.ssh should be blocked")

    def test_path_containing_sensitive_directory_is_blocked(self):
        """Path that contains a sensitive directory inside it should be blocked.

        For example, if the extra read path is the user's home directory, and
        ~/.ssh exists inside it, the path should be blocked because granting
        read access to the parent would expose the sensitive subdirectory.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            self._set_home(tmpdir)
            # Create a sensitive dir inside the home so it triggers the
            # "sensitive dir is inside the requested path" check
            ssh_dir = Path(tmpdir) / ".ssh"
            ssh_dir.mkdir()

            os.environ[EXTRA_READ_PATHS_VAR] = tmpdir
            result = get_extra_read_paths()
            self.assertEqual(result, [], "Home dir containing .ssh should be blocked")

    def test_valid_non_sensitive_path_is_allowed(self):
        """A valid directory that is NOT sensitive should be allowed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._set_home(tmpdir)
            # Create a non-sensitive directory under home
            docs_dir = Path(tmpdir) / "Documents" / "myproject"
            docs_dir.mkdir(parents=True)

            os.environ[EXTRA_READ_PATHS_VAR] = str(docs_dir)
            result = get_extra_read_paths()
            self.assertEqual(len(result), 1, "Non-sensitive path should be allowed")
            self.assertEqual(result[0], docs_dir.resolve())

    def test_all_blocklist_entries_are_checked(self):
        """Every directory in EXTRA_READ_PATHS_BLOCKLIST should actually be blocked."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._set_home(tmpdir)

            for sensitive_name in sorted(EXTRA_READ_PATHS_BLOCKLIST):
                sensitive_dir = Path(tmpdir) / sensitive_name
                sensitive_dir.mkdir(parents=True, exist_ok=True)

                os.environ[EXTRA_READ_PATHS_VAR] = str(sensitive_dir)
                result = get_extra_read_paths()
                self.assertEqual(
                    result, [],
                    f"Blocklist entry '{sensitive_name}' should be blocked"
                )

    def test_multiple_paths_mixed_sensitive_and_valid(self):
        """When given multiple paths, only non-sensitive ones should pass."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._set_home(tmpdir)

            # Create one sensitive and one valid directory
            ssh_dir = Path(tmpdir) / ".ssh"
            ssh_dir.mkdir()
            valid_dir = Path(tmpdir) / "projects"
            valid_dir.mkdir()

            os.environ[EXTRA_READ_PATHS_VAR] = f"{ssh_dir},{valid_dir}"
            result = get_extra_read_paths()
            self.assertEqual(len(result), 1, "Only the non-sensitive path should be returned")
            self.assertEqual(result[0], valid_dir.resolve())

    def test_empty_extra_read_paths_returns_empty(self):
        """Empty EXTRA_READ_PATHS should return empty list."""
        os.environ[EXTRA_READ_PATHS_VAR] = ""
        result = get_extra_read_paths()
        self.assertEqual(result, [])

    def test_unset_extra_read_paths_returns_empty(self):
        """Unset EXTRA_READ_PATHS should return empty list."""
        os.environ.pop(EXTRA_READ_PATHS_VAR, None)
        result = get_extra_read_paths()
        self.assertEqual(result, [])

    def test_nonexistent_path_is_skipped(self):
        """A path that does not exist should be skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            self._set_home(tmpdir)
            nonexistent = Path(tmpdir) / "does_not_exist"

            os.environ[EXTRA_READ_PATHS_VAR] = str(nonexistent)
            result = get_extra_read_paths()
            self.assertEqual(result, [])

    def test_relative_path_is_skipped(self):
        """A relative path should be skipped."""
        os.environ[EXTRA_READ_PATHS_VAR] = "relative/path"
        result = get_extra_read_paths()
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
