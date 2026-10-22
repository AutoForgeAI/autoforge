"""
Unit tests for the file-state error guard (issue #30).

Covers detection of Claude Code's "File has not been read yet" /
"File has been unexpectedly modified" errors, the stuck-loop abort in
run_agent_session(), and the file-editing rules appended to agent prompts.
"""

import asyncio
import unittest
from pathlib import Path

from agent import MAX_CONSECUTIVE_FILE_STATE_ERRORS, is_file_state_error, run_agent_session
from prompts import FILE_EDITING_RULES_MARKER, get_coding_prompt, with_file_editing_rules

NOT_READ = "<tool_use_error>File has not been read yet. Read it first before writing to it.</tool_use_error>"
MODIFIED = "File has been unexpectedly modified. Read it again before attempting to write it."


# Minimal stand-ins for SDK message types; agent.py dispatches on class name.
class TextBlock:
    def __init__(self, text):
        self.text = text


class ToolUseBlock:
    def __init__(self, id, name, input=None):
        self.id = id
        self.name = name
        self.input = input or {}


class ToolResultBlock:
    def __init__(self, tool_use_id, content, is_error=False):
        self.tool_use_id = tool_use_id
        self.content = content
        self.is_error = is_error


class AssistantMessage:
    def __init__(self, content):
        self.content = content


class UserMessage:
    def __init__(self, content):
        self.content = content


class FakeClient:
    def __init__(self, messages):
        self.messages = messages
        self.consumed = 0
        self.interrupted = False

    async def query(self, message):
        pass

    async def receive_response(self):
        for msg in self.messages:
            self.consumed += 1
            yield msg

    async def interrupt(self):
        self.interrupted = True


def tool_call(tool_id, name, result, is_error=False):
    return [
        AssistantMessage([ToolUseBlock(tool_id, name)]),
        UserMessage([ToolResultBlock(tool_id, result, is_error=is_error)]),
    ]


def run(client):
    return asyncio.run(run_agent_session(client, "prompt", Path(".")))


class TestIsFileStateError(unittest.TestCase):
    def test_detects_known_errors(self):
        assert is_file_state_error(NOT_READ)
        assert is_file_state_error(MODIFIED)
        assert is_file_state_error("File has been modified since read, either by the user or a linter")

    def test_ignores_other_errors(self):
        assert not is_file_state_error("String to replace not found in file.")
        assert not is_file_state_error("Command 'stat' is not in the allowed commands list")
        assert not is_file_state_error("")


class TestStuckLoopGuard(unittest.TestCase):
    def test_aborts_after_consecutive_file_state_errors(self):
        messages = []
        for i in range(MAX_CONSECUTIVE_FILE_STATE_ERRORS + 5):
            messages += tool_call(f"r{i}", "Read", "contents")
            messages += tool_call(f"e{i}", "Edit", MODIFIED, is_error=True)
        client = FakeClient(messages)

        status, response = run(client)

        assert status == "error"
        assert "consecutive Write/Edit errors" in response
        assert client.interrupted
        # Stopped as soon as the threshold was reached, not at the end of the stream
        assert client.consumed == MAX_CONSECUTIVE_FILE_STATE_ERRORS * 4

    def test_successful_write_resets_counter(self):
        messages = []
        for i in range(MAX_CONSECUTIVE_FILE_STATE_ERRORS * 3):
            messages += tool_call(f"w{i}", "Write", NOT_READ, is_error=True)
            if i % (MAX_CONSECUTIVE_FILE_STATE_ERRORS - 1) == 0:
                messages += tool_call(f"ok{i}", "Edit", "File updated successfully")
        messages.append(AssistantMessage([TextBlock("done")]))
        client = FakeClient(messages)

        status, response = run(client)

        assert status == "continue"
        assert response == "done"
        assert not client.interrupted

    def test_successful_read_does_not_reset_counter(self):
        messages = []
        for i in range(MAX_CONSECUTIVE_FILE_STATE_ERRORS):
            messages += tool_call(f"r{i}", "Read", "contents")
            messages += tool_call(f"b{i}", "Bash", "ok")
            messages += tool_call(f"e{i}", "Edit", MODIFIED, is_error=True)
        client = FakeClient(messages)

        status, _ = run(client)

        assert status == "error"
        assert client.interrupted

    def test_other_errors_do_not_trigger_guard(self):
        messages = []
        for i in range(MAX_CONSECUTIVE_FILE_STATE_ERRORS * 2):
            messages += tool_call(f"e{i}", "Edit", "String to replace not found in file.", is_error=True)
        client = FakeClient(messages)

        status, _ = run(client)

        assert status == "continue"
        assert not client.interrupted


class TestFileEditingRules(unittest.TestCase):
    def test_rules_appended_once(self):
        prompt = with_file_editing_rules("Do the work.")
        assert prompt.startswith("Do the work.")
        assert FILE_EDITING_RULES_MARKER in prompt
        assert "File has been unexpectedly modified" in prompt
        assert with_file_editing_rules(prompt) == prompt

    def test_rules_apply_to_template_prompt(self):
        prompt = with_file_editing_rules(get_coding_prompt())
        assert prompt.count(FILE_EDITING_RULES_MARKER) == 1


if __name__ == "__main__":
    unittest.main()
