"""
Chat Session System Prompt File Tests
=====================================

Chat sessions (assistant, spec, expand) must pass their system prompt to the
Claude CLI via ``--system-prompt-file`` rather than inline, because inline
prompts exceed the Windows command line length limit (GitHub issue #44), and
must never overwrite the project's CLAUDE.md.

Run with: python -m pytest test_chat_system_prompt.py -v
"""

import fnmatch
import logging
from pathlib import Path

from autoforge_paths import _GITIGNORE_CONTENT
from server.services.chat_constants import remove_system_prompt_file, write_system_prompt_file

logger = logging.getLogger(__name__)


def test_write_system_prompt_file_stores_prompt_in_autoforge_dir(tmp_path: Path) -> None:
    (tmp_path / "CLAUDE.md").write_text("user content", encoding="utf-8")
    prompt = "x" * 20000  # Larger than the Windows command line limit

    path = write_system_prompt_file(tmp_path, "assistant", prompt)

    assert path.is_absolute()
    assert path.parent == (tmp_path / ".autoforge").resolve()
    assert path.read_text(encoding="utf-8") == prompt
    assert (tmp_path / "CLAUDE.md").read_text(encoding="utf-8") == "user content"


def test_system_prompt_files_are_unique_per_session(tmp_path: Path) -> None:
    first = write_system_prompt_file(tmp_path, "assistant", "a")
    second = write_system_prompt_file(tmp_path, "assistant", "b")

    assert first != second
    assert first.read_text(encoding="utf-8") == "a"
    assert second.read_text(encoding="utf-8") == "b"


def test_remove_system_prompt_file(tmp_path: Path) -> None:
    path = write_system_prompt_file(tmp_path, "expand", "prompt")

    remove_system_prompt_file(path, logger)
    assert not path.exists()

    # Missing files and None are tolerated
    remove_system_prompt_file(path, logger)
    remove_system_prompt_file(None, logger)


def test_system_prompt_files_are_gitignored(tmp_path: Path) -> None:
    path = write_system_prompt_file(tmp_path, "spec", "prompt")
    patterns = [line for line in _GITIGNORE_CONTENT.splitlines() if line and not line.startswith("#")]

    assert any(fnmatch.fnmatch(path.name, pattern) for pattern in patterns)
