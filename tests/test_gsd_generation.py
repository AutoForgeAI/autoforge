from __future__ import annotations

from pathlib import Path

import pytest

from autocoder.generation.gsd import build_gsd_to_spec_prompt, get_gsd_status


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_gsd_status_missing(tmp_path: Path) -> None:
    st = get_gsd_status(tmp_path)
    assert st.exists is False
    assert set(st.missing) == {"ARCHITECTURE.md", "STACK.md", "STRUCTURE.md"}


def test_build_gsd_prompt(tmp_path: Path) -> None:
    base = tmp_path / ".planning" / "codebase"
    _write(base / "STACK.md", "Node + React")
    _write(base / "ARCHITECTURE.md", "Layers...")
    _write(base / "STRUCTURE.md", "src/ ...")

    prompt = build_gsd_to_spec_prompt(tmp_path)
    assert "GSD mapping docs" in prompt
    assert "STACK.md" in prompt
    assert "ARCHITECTURE.md" in prompt
    assert "STRUCTURE.md" in prompt

    # Optional file included when present
    _write(base / "CONVENTIONS.md", "Use prettier")
    prompt2 = build_gsd_to_spec_prompt(tmp_path)
    assert "CONVENTIONS.md" in prompt2


def test_build_gsd_prompt_raises_when_missing_required(tmp_path: Path) -> None:
    base = tmp_path / ".planning" / "codebase"
    _write(base / "STACK.md", "x")
    with pytest.raises(FileNotFoundError):
        build_gsd_to_spec_prompt(tmp_path)

