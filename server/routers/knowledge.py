"""
Knowledge Router
================

API endpoints for managing a project's knowledge files: user-supplied
markdown/text documents (requirements, research notes, ...) stored in
``{project}/.autoforge/knowledge/`` and referenced in every agent prompt.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..schemas import KnowledgeFileContent, KnowledgeFileInfo, KnowledgeFileUpload
from ..utils.project_helpers import get_project_path as _get_project_path
from ..utils.validation import validate_project_name

# Limits to keep prompts and disk usage sane
MAX_KNOWLEDGE_FILE_SIZE = 1024 * 1024  # 1 MB per file
MAX_KNOWLEDGE_FILES = 50

# Plain filenames only: no path separators, no leading dot, known text extension
_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._()-]{0,99}\.(md|markdown|txt)$", re.IGNORECASE)

router = APIRouter(
    prefix="/api/projects/{project_name}/knowledge",
    tags=["knowledge"],
)


def _get_project_dir(project_name: str) -> Path:
    """Resolve a registered project's directory or raise 404."""
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail=f"Project directory not found: {project_dir}")
    return project_dir


def _get_knowledge_dir(project_name: str) -> Path:
    """Resolve the knowledge directory for a registered project (not created)."""
    from autoforge_paths import get_knowledge_dir
    return get_knowledge_dir(_get_project_dir(project_name))


def _validate_filename(filename: str) -> str:
    """Reject anything that isn't a plain .md/.markdown/.txt filename."""
    if not _FILENAME_RE.match(filename) or ".." in filename:
        raise HTTPException(
            status_code=400,
            detail="Invalid filename. Use letters, numbers, spaces, '.', '_', '-', '(' or ')' "
                   "with a .md, .markdown or .txt extension.",
        )
    return filename


def _file_info(path: Path) -> KnowledgeFileInfo:
    stat = path.stat()
    return KnowledgeFileInfo(
        filename=path.name,
        size=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
    )


@router.get("", response_model=list[KnowledgeFileInfo])
async def list_knowledge_files(project_name: str) -> list[KnowledgeFileInfo]:
    """List the project's knowledge files."""
    from prompts import list_knowledge_files as _list_files

    return [_file_info(p) for p in _list_files(_get_project_dir(project_name))]


@router.get("/{filename}", response_model=KnowledgeFileContent)
async def get_knowledge_file(project_name: str, filename: str) -> KnowledgeFileContent:
    """Return a knowledge file's content."""
    path = _get_knowledge_dir(project_name) / _validate_filename(filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Knowledge file '{filename}' not found")
    return KnowledgeFileContent(filename=path.name, content=path.read_text(encoding="utf-8", errors="replace"))


@router.post("", response_model=KnowledgeFileInfo)
async def upload_knowledge_file(project_name: str, upload: KnowledgeFileUpload) -> KnowledgeFileInfo:
    """Create or overwrite a knowledge file."""
    knowledge_dir = _get_knowledge_dir(project_name)
    filename = _validate_filename(upload.filename)

    data = upload.content.encode("utf-8")
    if len(data) > MAX_KNOWLEDGE_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(data) / 1024:.0f} KB). Maximum is "
                   f"{MAX_KNOWLEDGE_FILE_SIZE // 1024} KB.",
        )

    path = knowledge_dir / filename
    if not path.exists() and knowledge_dir.is_dir():
        existing = sum(1 for p in knowledge_dir.iterdir() if p.is_file())
        if existing >= MAX_KNOWLEDGE_FILES:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum of {MAX_KNOWLEDGE_FILES} knowledge files per project reached",
            )

    knowledge_dir.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return _file_info(path)


@router.delete("/{filename}")
async def delete_knowledge_file(project_name: str, filename: str) -> dict:
    """Delete a knowledge file."""
    path = _get_knowledge_dir(project_name) / _validate_filename(filename)
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Knowledge file '{filename}' not found")
    path.unlink()
    return {"success": True, "message": f"Deleted {filename}"}
