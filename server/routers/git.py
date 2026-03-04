"""
Git Router
==========

API endpoints for git branch management.
Provides branch listing, checkout, and creation functionality.
"""

import re
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

# ============================================================================
# Helper Functions
# ============================================================================


def _get_project_path(project_name: str) -> Path | None:
    """Get project path from registry."""
    import sys
    root = Path(__file__).parent.parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from registry import get_project_path
    return get_project_path(project_name)


def validate_project_name(name: str) -> str:
    """Validate and sanitize project name to prevent path traversal."""
    if not re.match(r'^[a-zA-Z0-9_-]{1,50}$', name):
        raise HTTPException(
            status_code=400,
            detail="Invalid project name"
        )
    return name


def validate_branch_name(branch_name: str) -> str:
    """Validate git branch name.

    Git branch names have specific rules:
    - Cannot contain: space, ~, ^, :, ?, *, [, \\
    - Cannot start or end with /
    - Cannot contain consecutive slashes
    - Cannot end with .lock
    - Cannot be empty or just dots
    """
    if not branch_name or len(branch_name) > 250:
        raise HTTPException(
            status_code=400,
            detail="Branch name must be 1-250 characters"
        )

    # Check for invalid characters
    invalid_chars = re.compile(r'[\s~^:?*\[\]\\]')
    if invalid_chars.search(branch_name):
        raise HTTPException(
            status_code=400,
            detail="Branch name contains invalid characters"
        )

    # Check for patterns that are not allowed
    if (branch_name.startswith('/') or
        branch_name.endswith('/') or
        '//' in branch_name or
        branch_name.endswith('.lock') or
        branch_name == '.' or
        branch_name == '..' or
        branch_name.startswith('-')):
        raise HTTPException(
            status_code=400,
            detail="Invalid branch name format"
        )

    return branch_name


def run_git_command(project_dir: Path, *args, timeout: int = 30) -> tuple[bool, str]:
    """Run a git command and return (success, output).

    Args:
        project_dir: The directory to run the command in
        *args: Git command arguments (without 'git' prefix)
        timeout: Command timeout in seconds

    Returns:
        Tuple of (success: bool, output: str)
    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=project_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout.strip() or result.stderr.strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, "Git command timed out"
    except FileNotFoundError:
        return False, "Git is not installed or not in PATH"
    except Exception as e:
        return False, str(e)


def is_git_repo(project_dir: Path) -> bool:
    """Check if a directory is a git repository."""
    success, _ = run_git_command(project_dir, "rev-parse", "--git-dir")
    return success


def get_current_branch(project_dir: Path) -> str | None:
    """Get the current branch name."""
    success, output = run_git_command(project_dir, "rev-parse", "--abbrev-ref", "HEAD")
    if success and output:
        return output
    return None


def has_uncommitted_changes(project_dir: Path) -> bool:
    """Check if there are uncommitted changes in the repository."""
    # Check for staged changes
    success_staged, _ = run_git_command(project_dir, "diff", "--cached", "--quiet")
    if not success_staged:
        return True

    # Check for unstaged changes
    success_unstaged, _ = run_git_command(project_dir, "diff", "--quiet")
    if not success_unstaged:
        return True

    # Check for untracked files
    success, output = run_git_command(project_dir, "ls-files", "--others", "--exclude-standard")
    if success and output:
        return True

    return False


# ============================================================================
# Request/Response Schemas
# ============================================================================


# Protected branches that should not be directly modified
PROTECTED_BRANCHES = ["main", "master"]


class BranchInfo(BaseModel):
    """Information about a git branch."""
    name: str
    is_current: bool
    is_protected: bool


class BranchListResponse(BaseModel):
    """Response for branch listing."""
    is_git_repo: bool
    current_branch: str | None = None
    branches: list[BranchInfo] = Field(default_factory=list)
    protected_branches: list[str] = Field(default_factory=lambda: PROTECTED_BRANCHES.copy())
    has_uncommitted_changes: bool = False


class CheckoutRequest(BaseModel):
    """Request schema for checking out a branch."""
    branch: str = Field(..., min_length=1, max_length=250)

    @field_validator('branch')
    @classmethod
    def validate_branch(cls, v: str) -> str:
        """Validate branch name format."""
        # Basic validation - full validation happens in the endpoint
        if not v or not v.strip():
            raise ValueError("Branch name cannot be empty")
        return v.strip()


class CheckoutResponse(BaseModel):
    """Response for checkout operation."""
    success: bool
    previous_branch: str | None = None
    current_branch: str | None = None
    message: str = ""
    had_uncommitted_changes: bool = False


class CreateBranchRequest(BaseModel):
    """Request schema for creating a new branch."""
    branch_name: str = Field(..., min_length=1, max_length=250)
    from_branch: str | None = None  # If None, creates from current HEAD

    @field_validator('branch_name')
    @classmethod
    def validate_branch_name(cls, v: str) -> str:
        """Validate branch name format."""
        if not v or not v.strip():
            raise ValueError("Branch name cannot be empty")
        return v.strip()

    @field_validator('from_branch')
    @classmethod
    def validate_from_branch(cls, v: str | None) -> str | None:
        """Validate source branch name format."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v


class CreateBranchResponse(BaseModel):
    """Response for branch creation."""
    success: bool
    branch: str | None = None
    message: str = ""
    had_uncommitted_changes: bool = False


# ============================================================================
# Router
# ============================================================================


router = APIRouter(prefix="/api/projects/{project_name}/git", tags=["git"])


@router.get("/branches", response_model=BranchListResponse)
async def list_branches(project_name: str):
    """List all branches in the project repository.

    Returns information about all local branches, including which one is
    currently checked out and which branches are protected.
    """
    project_name = validate_project_name(project_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project_name}' not found in registry"
        )

    if not project_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project directory not found: {project_dir}"
        )

    # Check if it's a git repo
    if not is_git_repo(project_dir):
        return BranchListResponse(
            is_git_repo=False,
            current_branch=None,
            branches=[],
            protected_branches=PROTECTED_BRANCHES.copy(),
            has_uncommitted_changes=False,
        )

    # Get current branch
    current = get_current_branch(project_dir)

    # Get all local branches
    success, output = run_git_command(project_dir, "branch", "--list", "--format=%(refname:short)")
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list branches: {output}"
        )

    branch_names = [b.strip() for b in output.split('\n') if b.strip()]

    branches = [
        BranchInfo(
            name=name,
            is_current=(name == current),
            is_protected=(name in PROTECTED_BRANCHES),
        )
        for name in branch_names
    ]

    # Sort: current branch first, then protected, then alphabetically
    branches.sort(key=lambda b: (not b.is_current, not b.is_protected, b.name.lower()))

    # Check for uncommitted changes
    uncommitted = has_uncommitted_changes(project_dir)

    return BranchListResponse(
        is_git_repo=True,
        current_branch=current,
        branches=branches,
        protected_branches=PROTECTED_BRANCHES.copy(),
        has_uncommitted_changes=uncommitted,
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout_branch(project_name: str, request: CheckoutRequest):
    """Checkout an existing branch.

    Switches the working directory to the specified branch.
    Will warn (but not block) if there are uncommitted changes.
    """
    project_name = validate_project_name(project_name)
    target_branch = validate_branch_name(request.branch)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project_name}' not found in registry"
        )

    if not project_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project directory not found: {project_dir}"
        )

    if not is_git_repo(project_dir):
        raise HTTPException(
            status_code=400,
            detail="Directory is not a git repository"
        )

    # Get current branch before checkout
    previous_branch = get_current_branch(project_dir)

    # Check if target branch exists
    success, _ = run_git_command(project_dir, "rev-parse", "--verify", f"refs/heads/{target_branch}")
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Branch '{target_branch}' does not exist"
        )

    # Check for uncommitted changes (warning only)
    uncommitted = has_uncommitted_changes(project_dir)

    # Perform checkout
    success, output = run_git_command(project_dir, "checkout", target_branch)
    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to checkout branch: {output}"
        )

    # Verify the checkout
    new_current = get_current_branch(project_dir)

    return CheckoutResponse(
        success=True,
        previous_branch=previous_branch,
        current_branch=new_current,
        message=f"Switched to branch '{target_branch}'" + (" (with uncommitted changes)" if uncommitted else ""),
        had_uncommitted_changes=uncommitted,
    )


@router.post("/create-branch", response_model=CreateBranchResponse)
async def create_branch(project_name: str, request: CreateBranchRequest):
    """Create a new branch and switch to it.

    Creates a new branch from the specified source branch (or current HEAD
    if not specified) and checks it out.
    """
    project_name = validate_project_name(project_name)
    new_branch = validate_branch_name(request.branch_name)
    project_dir = _get_project_path(project_name)

    if not project_dir:
        raise HTTPException(
            status_code=404,
            detail=f"Project '{project_name}' not found in registry"
        )

    if not project_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project directory not found: {project_dir}"
        )

    if not is_git_repo(project_dir):
        raise HTTPException(
            status_code=400,
            detail="Directory is not a git repository"
        )

    # Validate from_branch if specified
    from_branch = None
    if request.from_branch:
        from_branch = validate_branch_name(request.from_branch)
        # Check if source branch exists
        success, _ = run_git_command(project_dir, "rev-parse", "--verify", f"refs/heads/{from_branch}")
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Source branch '{from_branch}' does not exist"
            )

    # Check if new branch already exists
    success, _ = run_git_command(project_dir, "rev-parse", "--verify", f"refs/heads/{new_branch}")
    if success:
        raise HTTPException(
            status_code=409,
            detail=f"Branch '{new_branch}' already exists"
        )

    # Check for uncommitted changes (warning only)
    uncommitted = has_uncommitted_changes(project_dir)

    # Create and checkout the new branch
    if from_branch:
        # Create from specific branch
        success, output = run_git_command(project_dir, "checkout", "-b", new_branch, from_branch)
    else:
        # Create from current HEAD
        success, output = run_git_command(project_dir, "checkout", "-b", new_branch)

    if not success:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create branch: {output}"
        )

    # Verify the branch was created and is now checked out
    current = get_current_branch(project_dir)
    if current != new_branch:
        raise HTTPException(
            status_code=500,
            detail=f"Branch creation verification failed: expected '{new_branch}', got '{current}'"
        )

    return CreateBranchResponse(
        success=True,
        branch=current,
        message=f"Created and switched to branch '{new_branch}'" + (f" from '{from_branch}'" if from_branch else "") + (" (with uncommitted changes)" if uncommitted else ""),
        had_uncommitted_changes=uncommitted,
    )
