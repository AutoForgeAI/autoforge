"""
GitHub Router
=============

Import GitHub issues from a project's repository as features.
"""

import asyncio
import logging
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..schemas import FeatureResponse
from ..services import github_issues as gh
from ..utils.project_helpers import get_project_path as _get_project_path
from ..utils.validation import validate_project_name
from .features import _get_db_classes, feature_to_response, get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects/{project_name}/github", tags=["github"])


class GitHubIssueItem(BaseModel):
    number: int
    title: str
    body: str
    state: str
    url: str
    labels: list[str]
    author: str
    comments: int
    created_at: str | None = None
    updated_at: str | None = None
    imported_feature_id: int | None = None


class GitHubIssueListResponse(BaseModel):
    repo: str
    authenticated: bool
    issues: list[GitHubIssueItem]


class GitHubRepoResponse(BaseModel):
    repo: str | None
    authenticated: bool


class GitHubImportRequest(BaseModel):
    repo: str
    issue_numbers: list[int] = Field(min_length=1, max_length=50)
    include_comments: bool = True


class GitHubImportResponse(BaseModel):
    created: int
    skipped: list[int]
    features: list[FeatureResponse]


def _resolve_project(project_name: str) -> Path:
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)
    if not project_dir:
        raise HTTPException(status_code=404, detail=f"Project '{project_name}' not found in registry")
    if not project_dir.exists():
        raise HTTPException(status_code=404, detail="Project directory not found")
    return project_dir


def _imported_issue_map(project_dir: Path, issues: list[dict]) -> dict[str, int]:
    """Map issue URL -> feature id for issues already imported into this project."""
    if not issues:
        return {}
    _, Feature = _get_db_classes()
    found: dict[str, int] = {}
    with get_db_session(project_dir) as session:
        for f in session.query(Feature.id, Feature.description).filter(
            Feature.description.contains("Source: https://github.com/")
        ):
            for issue in issues:
                if issue["url"] and gh.source_marker(issue["url"]) in (f.description or "").splitlines():
                    found[issue["url"]] = f.id
    return found


@router.get("/repo", response_model=GitHubRepoResponse)
async def get_repo(project_name: str):
    """Detect the project's GitHub repository from its git remotes."""
    project_dir = _resolve_project(project_name)
    repo = await asyncio.to_thread(gh.detect_repo, project_dir)
    auth = await asyncio.to_thread(gh.get_auth)
    return GitHubRepoResponse(repo=repo, authenticated=auth.token is not None)


@router.get("/issues", response_model=GitHubIssueListResponse)
async def list_issues(
    project_name: str,
    repo: str | None = None,
    state: Literal["open", "closed", "all"] = "open",
):
    """List a repository's issues, marking those already imported as features."""
    project_dir = _resolve_project(project_name)

    if not repo:
        repo = await asyncio.to_thread(gh.detect_repo, project_dir)
        if not repo:
            raise HTTPException(
                status_code=400,
                detail="No GitHub remote found for this project. Enter the repository as owner/name.",
            )

    try:
        repo = gh.validate_repo(repo)
        auth = await asyncio.to_thread(gh.get_auth)
        issues = await asyncio.to_thread(gh.list_issues, repo, auth, state)
    except gh.GitHubError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    imported = _imported_issue_map(project_dir, issues)
    return GitHubIssueListResponse(
        repo=repo,
        authenticated=auth.token is not None,
        issues=[GitHubIssueItem(**i, imported_feature_id=imported.get(i["url"])) for i in issues],
    )


@router.post("/import", response_model=GitHubImportResponse)
async def import_issues(project_name: str, request: GitHubImportRequest):
    """Create pending features from the selected GitHub issues.

    Issues that were already imported into this project are skipped.
    """
    project_dir = _resolve_project(project_name)

    try:
        repo = gh.validate_repo(request.repo)
        auth = await asyncio.to_thread(gh.get_auth)
        numbers = list(dict.fromkeys(n for n in request.issue_numbers if n > 0))
        if not numbers:
            raise HTTPException(status_code=400, detail="No valid issue numbers given")

        issues = []
        for number in numbers:
            issue = await asyncio.to_thread(gh.get_issue, repo, number, auth)
            comments = []
            if request.include_comments and issue["comments"]:
                comments = await asyncio.to_thread(gh.get_issue_comments, repo, number, auth)
            issues.append((issue, comments))
    except gh.GitHubError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))

    already = _imported_issue_map(project_dir, [i for i, _ in issues])
    _, Feature = _get_db_classes()

    skipped: list[int] = []
    try:
        with get_db_session(project_dir) as session:
            max_priority = session.query(Feature).order_by(Feature.priority.desc()).first()
            priority = (max_priority.priority + 1) if max_priority else 1

            created_ids = []
            for issue, comments in issues:
                if issue["url"] in already:
                    skipped.append(issue["number"])
                    continue
                fields = gh.issue_to_feature(repo, issue, comments)
                db_feature = Feature(
                    priority=priority,
                    passes=False,
                    in_progress=False,
                    **fields,
                )
                session.add(db_feature)
                session.flush()
                created_ids.append(db_feature.id)
                priority += 1

            session.commit()

            created = [
                feature_to_response(f)
                for f in session.query(Feature).filter(Feature.id.in_(created_ids)).order_by(Feature.priority)
            ]
    except Exception:
        logger.exception("Failed to import GitHub issues")
        raise HTTPException(status_code=500, detail="Failed to import GitHub issues")

    return GitHubImportResponse(created=len(created), skipped=skipped, features=created)
