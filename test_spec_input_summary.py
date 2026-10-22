"""
Tests for the spec creation conversation summary (spec_input_summary.md).

Covers markdown rendering of the conversation and persisting it to the
project's prompts directory once the spec is complete.
"""

import asyncio
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from server.schemas import FileAttachment
from server.services.spec_chat_session import (
    SPEC_SUMMARY_FILENAME,
    SpecChatSession,
    render_spec_input_summary,
)


class TestRenderSpecInputSummary(unittest.TestCase):
    def test_initial_prompt_questions_and_answers(self):
        messages = [
            {"role": "assistant", "content": "Hi! What do you want to build?"},
            {"role": "user", "content": "A todo app for teams"},
            {"role": "assistant", "content": "Which mode?"},
            {"role": "assistant", "content": "1. Quick\n2. Detailed"},
            {"role": "user", "content": "Quick"},
        ]
        md = render_spec_input_summary("my-app", messages, datetime(2026, 1, 2, 3, 4, 5))

        assert md.startswith("# Spec Creation Conversation: my-app\n")
        assert "- Started: 2026-01-02 03:04:05" in md

        initial = md.split("## Initial Prompt")[1].split("## Conversation")[0]
        assert "> A todo app for teams" in initial

        convo = md.split("## Conversation")[1]
        # Consecutive assistant chunks merge into one turn
        assert convo.count("### Claude") == 2
        assert "Which mode?\n\n1. Quick\n2. Detailed" in convo
        assert "### You (initial prompt)" in convo
        assert "> Quick" in convo
        # Order is preserved
        assert convo.index("What do you want") < convo.index("todo app") < convo.index("> Quick")

    def test_multiline_and_attachments(self):
        messages = [
            {"role": "user", "content": "line one\n\nline two", "attachments": ["mock.png"]},
        ]
        md = render_spec_input_summary("p", messages, datetime.now())
        assert "> line one\n>\n> line two" in md
        assert "> _Attachments: mock.png_" in md

    def test_no_user_input(self):
        md = render_spec_input_summary("p", [{"role": "assistant", "content": "Hello"}], datetime.now())
        assert "_No user input recorded._" in md


class TestWriteSpecInputSummary(unittest.TestCase):
    def test_written_to_prompts_dir_after_spec_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            session = SpecChatSession("demo", project_dir)
            session.client = object()  # bypass "not initialized" guard

            async def fake_query(message, attachments=None):
                session.messages.append({"role": "assistant", "content": "Spec written."})
                session.complete = True
                yield {"type": "spec_complete", "path": "app_spec.txt"}

            session._query_claude = fake_query

            attachment = FileAttachment(filename="notes.txt", mimeType="text/plain", base64Data="aGk=")

            async def run():
                return [c async for c in session.send_message("Build a blog", [attachment])]

            chunks = asyncio.run(run())
            assert chunks[-1] == {"type": "response_done"}

            summary = project_dir / ".autoforge" / "prompts" / SPEC_SUMMARY_FILENAME
            assert summary.exists()
            text = summary.read_text(encoding="utf-8")
            assert "> Build a blog" in text
            assert "notes.txt" in text
            assert "Spec written." in text

    def test_not_written_before_spec_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp)
            session = SpecChatSession("demo", project_dir)
            session.client = object()

            async def fake_query(message, attachments=None):
                session.messages.append({"role": "assistant", "content": "Tell me more."})
                yield {"type": "text", "content": "Tell me more."}

            session._query_claude = fake_query

            async def run():
                return [c async for c in session.send_message("Build a blog")]

            asyncio.run(run())
            assert not list(project_dir.rglob(SPEC_SUMMARY_FILENAME))


if __name__ == "__main__":
    unittest.main()
