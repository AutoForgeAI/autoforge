"""
Tests for passing chat-session system prompts via file (issue #8).

Long system prompts must not be passed on the command line, because Windows
limits command lines to ~8191 characters ("The command line is too long.").
"""

from claude_agent_sdk import ClaudeAgentOptions
from claude_agent_sdk._internal.transport.subprocess_cli import SubprocessCLITransport

from server.services.chat_constants import remove_system_prompt_file, write_system_prompt_file


def test_write_and_remove_system_prompt_file(tmp_path):
    prompt = "x" * 20000 + " ünïcode"
    path = write_system_prompt_file(tmp_path, "spec", prompt)

    assert path.exists()
    assert path.parent == (tmp_path / ".autoforge").resolve()
    assert path.read_text(encoding="utf-8") == prompt
    # Runtime file is gitignored
    assert ".system_prompt.*.md" in (tmp_path / ".autoforge" / ".gitignore").read_text(encoding="utf-8")
    # Does not touch the project's CLAUDE.md
    assert not (tmp_path / "CLAUDE.md").exists()

    remove_system_prompt_file(path)
    assert not path.exists()
    # Idempotent and tolerant of None
    remove_system_prompt_file(path)
    remove_system_prompt_file(None)


def test_unique_file_per_session(tmp_path):
    a = write_system_prompt_file(tmp_path, "expand", "a")
    b = write_system_prompt_file(tmp_path, "expand", "b")
    assert a != b
    assert a.read_text(encoding="utf-8") == "a"
    assert b.read_text(encoding="utf-8") == "b"


def test_prompt_not_on_command_line(tmp_path):
    prompt = "LONG_PROMPT_MARKER " + "y" * 20000
    path = write_system_prompt_file(tmp_path, "spec", prompt)
    options = ClaudeAgentOptions(
        system_prompt={"type": "file", "path": str(path)},
        cli_path="claude",
        cwd=str(tmp_path),
    )
    cmd = SubprocessCLITransport(prompt="", options=options)._build_command()

    assert "--system-prompt-file" in cmd
    assert cmd[cmd.index("--system-prompt-file") + 1] == str(path)
    assert not any("LONG_PROMPT_MARKER" in arg for arg in cmd)
    assert len(" ".join(cmd)) < 8191
