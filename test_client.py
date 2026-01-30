#!/usr/bin/env python3
"""
Client Utility Tests
====================

Tests for the client module utility functions.
Run with: python test_client.py
"""

import os
import unittest

from client import convert_model_for_vertex


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
            convert_model_for_vertex("claude-opus-4-5-20251101"),
            "claude-opus-4-5-20251101",
        )

    def test_returns_model_unchanged_when_vertex_set_to_zero(self):
        os.environ["CLAUDE_CODE_USE_VERTEX"] = "0"
        self.assertEqual(
            convert_model_for_vertex("claude-opus-4-5-20251101"),
            "claude-opus-4-5-20251101",
        )

    def test_returns_model_unchanged_when_vertex_set_to_empty(self):
        os.environ["CLAUDE_CODE_USE_VERTEX"] = ""
        self.assertEqual(
            convert_model_for_vertex("claude-sonnet-4-5-20250929"),
            "claude-sonnet-4-5-20250929",
        )

    # --- Vertex AI enabled: standard conversions ---

    def test_converts_opus_model(self):
        os.environ["CLAUDE_CODE_USE_VERTEX"] = "1"
        self.assertEqual(
            convert_model_for_vertex("claude-opus-4-5-20251101"),
            "claude-opus-4-5@20251101",
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
            convert_model_for_vertex("claude-opus-4-5@20251101"),
            "claude-opus-4-5@20251101",
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
            convert_model_for_vertex("claude-opus-4-5"),
            "claude-opus-4-5",
        )

    def test_empty_string_unchanged(self):
        os.environ["CLAUDE_CODE_USE_VERTEX"] = "1"
        self.assertEqual(convert_model_for_vertex(""), "")


if __name__ == "__main__":
    unittest.main()
