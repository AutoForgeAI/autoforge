"""
Git Router
==========

API endpoints for git status and operations.
"""

import subprocess
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/git", tags=["git"])


# Error types for structured error reporting
ErrorType = Literal[
    "git_not_installed",
    "not_a_repo",
    "auth_failed",
    "timeout",
    "no_remote",
    "network",
    "unknown",
]


class GitError(BaseModel):
    """Structured git error information."""
    error_type: ErrorType
    message: str
    action: str  # Suggested remediation


def classify_git_error(error_message: str) -> GitError:
    """Classify a git error and provide structured information."""
    lower = error_message.lower()

    if "not installed" in lower or "not found" in lower:
        return GitError(
            error_type="git_not_installed",
            message="Git is not installed on this system",
            action="Install Git from https://git-scm.com/downloads",
        )

    if "timed out" in lower:
        return GitError(
            error_type="timeout",
            message="Git command timed out",
            action="Check your network connection or try again",
        )

    if "authentication" in lower or "permission denied" in lower or "403" in lower:
        return GitError(
            error_type="auth_failed",
            message="Git authentication failed",
            action="Check your SSH keys or GitHub credentials",
        )

    if "could not resolve" in lower or "unable to access" in lower or "network" in lower:
        return GitError(
            error_type="network",
            message="Network error connecting to remote",
            action="Check your internet connection",
        )

    if "no such remote" in lower or "no upstream" in lower or "does not have upstream" in lower:
        return GitError(
            error_type="no_remote",
            message="No remote configured for this branch",
            action="Run: git push -u origin <branch>",
        )

    return GitError(
        error_type="unknown",
        message=error_message or "Unknown error",
        action="Check the git output for details",
    )


def run_git_command(project_path: Path, args: list[str]) -> tuple[bool, str, GitError | None]:
    """
    Run a git command in the project directory.

    Returns:
        Tuple of (success, output/error message, structured error if failed)
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, result.stdout.strip(), None
        error = classify_git_error(result.stderr.strip())
        return False, result.stderr.strip(), error
    except subprocess.TimeoutExpired:
        error = classify_git_error("Git command timed out")
        return False, "Git command timed out", error
    except FileNotFoundError:
        error = classify_git_error("Git is not installed")
        return False, "Git is not installed", error
    except Exception as e:
        error = classify_git_error(str(e))
        return False, str(e), error


def get_git_status_for_project(project_path: Path) -> dict:
    """
    Get comprehensive git status for a project.

    Returns:
        Dictionary with git status information.
    """
    # Check if it's a git repo
    success, _, error = run_git_command(project_path, ["rev-parse", "--git-dir"])
    if not success:
        # Check if it's "not a git repo" vs an actual error
        if error and error.error_type == "git_not_installed":
            return {
                "isRepo": False,
                "branch": None,
                "ahead": 0,
                "behind": 0,
                "modified": 0,
                "staged": 0,
                "untracked": 0,
                "hasUncommittedChanges": False,
                "lastCommitMessage": None,
                "lastCommitDate": None,
                "error": error.model_dump() if error else None,
            }
        return {
            "isRepo": False,
            "branch": None,
            "ahead": 0,
            "behind": 0,
            "modified": 0,
            "staged": 0,
            "untracked": 0,
            "hasUncommittedChanges": False,
            "lastCommitMessage": None,
            "lastCommitDate": None,
            "error": None,
        }

    # Get current branch
    success, branch, _ = run_git_command(project_path, ["rev-parse", "--abbrev-ref", "HEAD"])
    if not success:
        branch = None

    # Get ahead/behind counts
    ahead = 0
    behind = 0
    remote_error = None
    if branch:
        success, counts, error = run_git_command(
            project_path,
            ["rev-list", "--left-right", "--count", f"{branch}...@{{upstream}}"],
        )
        if success and counts:
            parts = counts.split()
            if len(parts) >= 2:
                ahead = int(parts[0])
                behind = int(parts[1])
        elif error:
            # Save remote error to include in response
            remote_error = error

    # Get status counts using porcelain format
    modified = 0
    staged = 0
    untracked = 0
    success, status_output, _ = run_git_command(project_path, ["status", "--porcelain"])
    if success:
        for line in status_output.split("\n"):
            if not line:
                continue
            index_status = line[0] if len(line) > 0 else " "
            worktree_status = line[1] if len(line) > 1 else " "

            # Staged changes (index)
            if index_status in "MADRC":
                staged += 1

            # Modified in worktree
            if worktree_status in "MD":
                modified += 1

            # Untracked
            if index_status == "?" and worktree_status == "?":
                untracked += 1

    has_uncommitted = (modified + staged + untracked) > 0

    # Get last commit info
    last_commit_message = None
    last_commit_date = None
    success, log_output, _ = run_git_command(
        project_path,
        ["log", "-1", "--format=%s|||%ci"],
    )
    if success and log_output:
        parts = log_output.split("|||")
        if len(parts) >= 1:
            last_commit_message = parts[0]
        if len(parts) >= 2:
            last_commit_date = parts[1]

    return {
        "isRepo": True,
        "branch": branch,
        "ahead": ahead,
        "behind": behind,
        "modified": modified,
        "staged": staged,
        "untracked": untracked,
        "hasUncommittedChanges": has_uncommitted,
        "lastCommitMessage": last_commit_message,
        "lastCommitDate": last_commit_date,
        "error": remote_error.model_dump() if remote_error else None,
    }


@router.get("/status/{project_name}")
async def get_git_status(project_name: str):
    """
    Get git status for a project.

    Args:
        project_name: The project name.

    Returns:
        Git status information.
    """
    import sys

    # Import registry to get project path
    root_dir = Path(__file__).parent.parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    from registry import get_project_path

    project_path = get_project_path(project_name)
    if project_path is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")

    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {project_path}")

    return get_git_status_for_project(project_path)


@router.post("/status/{project_name}/refresh")
async def refresh_git_status(project_name: str):
    """
    Force refresh git status (useful after git operations).

    Args:
        project_name: The project name.

    Returns:
        Fresh git status information.
    """
    return await get_git_status(project_name)


class InitGitRequest(BaseModel):
    """Request to initialize git repository."""

    initialBranch: str = "main"


class SetRemoteRequest(BaseModel):
    """Request to set git remote."""

    url: str
    name: str = "origin"


class CheckpointRequest(BaseModel):
    """Request to create a checkpoint commit."""

    message: str
    description: str | None = None


class CheckpointResponse(BaseModel):
    """Response from checkpoint commit."""

    success: bool
    commitHash: str | None = None
    message: str
    filesCommitted: int = 0


@router.post("/checkpoint/{project_name}", response_model=CheckpointResponse)
async def create_checkpoint(project_name: str, request: CheckpointRequest):
    """
    Create a checkpoint commit with all current changes.

    Stages all changes (tracked and untracked) and creates a commit
    with the provided message and optional description.

    Args:
        project_name: The project name.
        request: Checkpoint request with commit message.

    Returns:
        Checkpoint response with commit hash and details.
    """
    import sys

    # Import registry to get project path
    root_dir = Path(__file__).parent.parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    from registry import get_project_path

    project_path = get_project_path(project_name)
    if project_path is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")

    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {project_path}")

    # Check if it's a git repo
    success, _, error = run_git_command(project_path, ["rev-parse", "--git-dir"])
    if not success:
        # Try to initialize git
        success, _, error = run_git_command(project_path, ["init"])
        if not success:
            return CheckpointResponse(
                success=False,
                message=f"Failed to initialize git: {error.message if error else 'Unknown error'}",
            )

    # Stage all changes (use "." to be more forgiving with nested repos)
    success, output, error = run_git_command(project_path, ["add", "."])
    if not success:
        # Check for nested repo issue
        error_msg = error.message if error else output or 'Unknown error'
        if "does not have a commit checked out" in error_msg:
            # Extract the problematic directory name
            import re
            match = re.search(r"'([^']+)' does not have a commit checked out", error_msg)
            nested_dir = match.group(1) if match else "a subdirectory"
            return CheckpointResponse(
                success=False,
                message=f"Nested git repo '{nested_dir}' has no commit. Remove it, add to .gitignore, or initialize it as a submodule.",
            )
        return CheckpointResponse(
            success=False,
            message=f"Failed to stage changes: {error_msg}",
        )

    # Check if there are any staged changes
    success, status_output, _ = run_git_command(project_path, ["status", "--porcelain"])
    if success and not status_output.strip():
        return CheckpointResponse(
            success=False,
            message="No changes to commit",
            filesCommitted=0,
        )

    # Count files to be committed
    files_count = len([line for line in status_output.split("\n") if line.strip()])

    # Build commit message
    commit_message = request.message
    if request.description:
        commit_message += f"\n\n{request.description}"

    # Add co-author attribution
    commit_message += "\n\nCo-Authored-By: Claude <noreply@anthropic.com>"

    # Create the commit
    success, output, error = run_git_command(
        project_path,
        ["commit", "-m", commit_message],
    )
    if not success:
        return CheckpointResponse(
            success=False,
            message=f"Failed to commit: {error.message if error else output}",
        )

    # Get the commit hash
    success, commit_hash, _ = run_git_command(project_path, ["rev-parse", "--short", "HEAD"])

    return CheckpointResponse(
        success=True,
        commitHash=commit_hash if success else None,
        message=f"Created checkpoint: {request.message}",
        filesCommitted=files_count,
    )


@router.get("/diff/{project_name}")
async def get_git_diff(project_name: str):
    """
    Get the current diff for a project.

    Args:
        project_name: The project name.

    Returns:
        Git diff information.
    """
    import sys

    # Import registry to get project path
    root_dir = Path(__file__).parent.parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    from registry import get_project_path

    project_path = get_project_path(project_name)
    if project_path is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")

    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {project_path}")

    # Get staged diff
    success, staged_diff, _ = run_git_command(project_path, ["diff", "--cached", "--stat"])

    # Get unstaged diff
    success, unstaged_diff, _ = run_git_command(project_path, ["diff", "--stat"])

    # Get list of untracked files
    success, untracked, _ = run_git_command(
        project_path,
        ["ls-files", "--others", "--exclude-standard"],
    )

    return {
        "stagedDiff": staged_diff if staged_diff else None,
        "unstagedDiff": unstaged_diff if unstaged_diff else None,
        "untrackedFiles": untracked.split("\n") if untracked else [],
    }


@router.post("/init/{project_name}")
async def init_git_repo(project_name: str, request: InitGitRequest):
    """
    Initialize a git repository in the project directory.

    Args:
        project_name: The project name.
        request: Init request with optional initial branch name.

    Returns:
        Success status and message.
    """
    import sys

    root_dir = Path(__file__).parent.parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    from registry import get_project_path

    project_path = get_project_path(project_name)
    if project_path is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")

    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {project_path}")

    # Check if already a git repo
    success, _, _ = run_git_command(project_path, ["rev-parse", "--git-dir"])
    if success:
        return {"success": False, "message": "Already a git repository"}

    # Initialize git
    success, output, error = run_git_command(
        project_path,
        ["init", "-b", request.initialBranch],
    )
    if not success:
        return {
            "success": False,
            "message": f"Failed to initialize git: {error.message if error else output}",
        }

    return {"success": True, "message": f"Initialized git repository with branch '{request.initialBranch}'"}


@router.get("/remotes/{project_name}")
async def get_git_remotes(project_name: str):
    """
    Get list of git remotes for a project.

    Args:
        project_name: The project name.

    Returns:
        List of remotes with their URLs.
    """
    import sys

    root_dir = Path(__file__).parent.parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    from registry import get_project_path

    project_path = get_project_path(project_name)
    if project_path is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")

    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {project_path}")

    # Check if it's a git repo
    success, _, _ = run_git_command(project_path, ["rev-parse", "--git-dir"])
    if not success:
        return {"remotes": [], "isRepo": False}

    # Get remotes with URLs
    success, output, _ = run_git_command(project_path, ["remote", "-v"])
    if not success or not output:
        return {"remotes": [], "isRepo": True}

    # Parse remote output
    remotes = {}
    for line in output.split("\n"):
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 2:
            name = parts[0]
            url = parts[1]
            # Only keep fetch URL (skip push duplicates)
            if "(fetch)" in line or name not in remotes:
                remotes[name] = url

    return {
        "remotes": [{"name": name, "url": url} for name, url in remotes.items()],
        "isRepo": True,
    }


@router.post("/remotes/{project_name}")
async def set_git_remote(project_name: str, request: SetRemoteRequest):
    """
    Add or update a git remote.

    Args:
        project_name: The project name.
        request: Remote configuration with name and URL.

    Returns:
        Success status and message.
    """
    import sys

    root_dir = Path(__file__).parent.parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    from registry import get_project_path

    project_path = get_project_path(project_name)
    if project_path is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")

    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {project_path}")

    # Check if it's a git repo
    success, _, _ = run_git_command(project_path, ["rev-parse", "--git-dir"])
    if not success:
        return {"success": False, "message": "Not a git repository. Initialize git first."}

    # Check if remote already exists
    success, remotes, _ = run_git_command(project_path, ["remote"])
    remote_exists = request.name in (remotes.split("\n") if remotes else [])

    if remote_exists:
        # Update existing remote
        success, output, error = run_git_command(
            project_path,
            ["remote", "set-url", request.name, request.url],
        )
    else:
        # Add new remote
        success, output, error = run_git_command(
            project_path,
            ["remote", "add", request.name, request.url],
        )

    if not success:
        return {
            "success": False,
            "message": f"Failed to set remote: {error.message if error else output}",
        }

    action = "Updated" if remote_exists else "Added"
    return {"success": True, "message": f"{action} remote '{request.name}' -> {request.url}"}


@router.delete("/remotes/{project_name}/{remote_name}")
async def remove_git_remote(project_name: str, remote_name: str):
    """
    Remove a git remote.

    Args:
        project_name: The project name.
        remote_name: The remote to remove.

    Returns:
        Success status and message.
    """
    import sys

    root_dir = Path(__file__).parent.parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    from registry import get_project_path

    project_path = get_project_path(project_name)
    if project_path is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")

    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {project_path}")

    success, output, error = run_git_command(
        project_path,
        ["remote", "remove", remote_name],
    )

    if not success:
        return {
            "success": False,
            "message": f"Failed to remove remote: {error.message if error else output}",
        }

    return {"success": True, "message": f"Removed remote '{remote_name}'"}


# =============================================================================
# Worktree Endpoints
# =============================================================================


class WorktreeCreateRequest(BaseModel):
    """Request to create a worktree."""

    fromBranch: str | None = None


class WorktreeMergeRequest(BaseModel):
    """Request to merge worktree changes."""

    commitMessage: str | None = None
    deleteAfter: bool = True


class WorktreeActionResponse(BaseModel):
    """Response from worktree actions."""

    success: bool
    message: str


@router.get("/worktree/{project_name}/status")
async def get_worktree_status(project_name: str):
    """
    Get the worktree status for a project.

    Args:
        project_name: The project name.

    Returns:
        Worktree status information.
    """
    import sys

    root_dir = Path(__file__).parent.parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    from registry import get_project_path
    from server.services.worktree_manager import get_worktree_manager

    project_path = get_project_path(project_name)
    if project_path is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")

    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {project_path}")

    manager = get_worktree_manager(project_name, project_path)
    return manager.get_status()


@router.get("/worktree/{project_name}/diff")
async def get_worktree_diff(project_name: str):
    """
    Get the diff between worktree and main branch.

    Args:
        project_name: The project name.

    Returns:
        Diff information.
    """
    import sys

    root_dir = Path(__file__).parent.parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    from registry import get_project_path
    from server.services.worktree_manager import get_worktree_manager

    project_path = get_project_path(project_name)
    if project_path is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")

    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {project_path}")

    manager = get_worktree_manager(project_name, project_path)
    return manager.get_diff()


@router.post("/worktree/{project_name}/create", response_model=WorktreeActionResponse)
async def create_worktree(project_name: str, request: WorktreeCreateRequest | None = None):
    """
    Create a worktree for the project.

    Args:
        project_name: The project name.
        request: Optional request with fromBranch parameter.

    Returns:
        Success status and message.
    """
    import sys

    root_dir = Path(__file__).parent.parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    from registry import get_project_path, set_project_worktree_path
    from server.services.worktree_manager import get_worktree_manager

    project_path = get_project_path(project_name)
    if project_path is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")

    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {project_path}")

    manager = get_worktree_manager(project_name, project_path)
    from_branch = request.fromBranch if request else None
    success, message = manager.create(from_branch=from_branch)

    if success:
        # Store worktree path in registry
        set_project_worktree_path(project_name, manager.worktree_path)

    return WorktreeActionResponse(success=success, message=message)


@router.post("/worktree/{project_name}/merge", response_model=WorktreeActionResponse)
async def merge_worktree(project_name: str, request: WorktreeMergeRequest | None = None):
    """
    Merge worktree changes back to main branch.

    Args:
        project_name: The project name.
        request: Optional request with merge options.

    Returns:
        Success status and message.
    """
    import sys

    root_dir = Path(__file__).parent.parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    from registry import clear_project_worktree_path, get_project_path
    from server.services.worktree_manager import get_worktree_manager

    project_path = get_project_path(project_name)
    if project_path is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")

    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {project_path}")

    manager = get_worktree_manager(project_name, project_path)
    commit_message = request.commitMessage if request else None
    delete_after = request.deleteAfter if request else True

    success, message = manager.merge_to_main(
        commit_message=commit_message,
        delete_after=delete_after
    )

    if success and delete_after:
        # Clear worktree path from registry
        clear_project_worktree_path(project_name)

    return WorktreeActionResponse(success=success, message=message)


@router.post("/worktree/{project_name}/stage", response_model=WorktreeActionResponse)
async def stage_worktree_changes(project_name: str):
    """
    Stage worktree changes in main project without committing.

    Allows user to review changes before committing.

    Args:
        project_name: The project name.

    Returns:
        Success status and message.
    """
    import sys

    root_dir = Path(__file__).parent.parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    from registry import get_project_path
    from server.services.worktree_manager import get_worktree_manager

    project_path = get_project_path(project_name)
    if project_path is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")

    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {project_path}")

    manager = get_worktree_manager(project_name, project_path)
    success, message = manager.stage_changes()

    return WorktreeActionResponse(success=success, message=message)


@router.delete("/worktree/{project_name}", response_model=WorktreeActionResponse)
async def discard_worktree(project_name: str):
    """
    Discard worktree changes and remove the worktree.

    Args:
        project_name: The project name.

    Returns:
        Success status and message.
    """
    import sys

    root_dir = Path(__file__).parent.parent.parent
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))

    from registry import clear_project_worktree_path, get_project_path
    from server.services.worktree_manager import get_worktree_manager

    project_path = get_project_path(project_name)
    if project_path is None:
        raise HTTPException(status_code=404, detail=f"Project not found: {project_name}")

    if not project_path.exists():
        raise HTTPException(status_code=404, detail=f"Project path does not exist: {project_path}")

    manager = get_worktree_manager(project_name, project_path)
    success, message = manager.discard()

    if success:
        # Clear worktree path from registry
        clear_project_worktree_path(project_name)

    return WorktreeActionResponse(success=success, message=message)
