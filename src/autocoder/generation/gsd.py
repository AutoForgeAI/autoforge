from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REQUIRED_FILES = ("STACK.md", "ARCHITECTURE.md", "STRUCTURE.md")
OPTIONAL_FILES = ("CONVENTIONS.md", "INTEGRATIONS.md")


@dataclass(frozen=True)
class GsdStatus:
    exists: bool
    codebase_dir: Path
    present: list[str]
    missing: list[str]


def gsd_codebase_dir(project_dir: Path) -> Path:
    return Path(project_dir).resolve() / ".planning" / "codebase"


def get_gsd_status(project_dir: Path) -> GsdStatus:
    base = gsd_codebase_dir(project_dir)
    exists = base.exists() and base.is_dir()
    present: list[str] = []
    missing: list[str] = []

    for name in REQUIRED_FILES:
        if exists and (base / name).exists():
            present.append(name)
        else:
            missing.append(name)

    for name in OPTIONAL_FILES:
        if exists and (base / name).exists():
            present.append(name)

    return GsdStatus(exists=exists, codebase_dir=base, present=sorted(present), missing=sorted(missing))


def _read_text(path: Path, *, max_chars: int) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[TRUNCATED]\n"
    return text


def build_gsd_to_spec_prompt(project_dir: Path, *, max_file_chars: int = 120_000) -> str:
    """
    Build a prompt that converts GSD mapping docs into an AutoCoder app_spec.txt.
    """
    st = get_gsd_status(project_dir)
    if not st.exists or st.missing:
        missing = ", ".join(st.missing) if st.missing else "unknown"
        raise FileNotFoundError(f"GSD mapping not found or incomplete (missing: {missing})")

    docs: list[tuple[str, str]] = []
    for name in (*REQUIRED_FILES, *OPTIONAL_FILES):
        p = st.codebase_dir / name
        if p.exists():
            docs.append((name, _read_text(p, max_chars=max_file_chars)))

    project_dir = Path(project_dir).resolve()
    project_name = project_dir.name

    joined = "\n\n".join([f"# {name}\n\n{content}" for name, content in docs if content.strip()])

    return (
        "Convert the following GSD codebase mapping into an AutoCoder `prompts/app_spec.txt`.\n"
        "The goal is to onboard an existing project to AutoCoder so it can generate a feature backlog.\n\n"
        f"Project name: {project_name}\n\n"
        "GSD mapping docs (from `.planning/codebase/*.md`):\n\n"
        f"{joined}\n\n"
        "Requirements:\n"
        "- Reflect the existing architecture and conventions.\n"
        "- Prefer specific, testable features grouped by category.\n"
        "- Include any setup/test/lint/typecheck commands if mentioned.\n"
        "- Include key routes/endpoints if mentioned.\n"
    )
