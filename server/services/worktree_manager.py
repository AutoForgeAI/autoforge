"""
Worktree Manager
================

Manages git worktrees for autocoder projects.
Provides isolation so agent work happens in a worktree, not the main directory.
"""

import logging
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Worktree base directory under user's home
WORKTREE_BASE = Path.home() / ".autocoder" / "worktrees"

# Branch name used for autocoder work
WORKTREE_BRANCH_PREFIX = "autocoder-work"


def run_git_command(
    cwd: Path, args: list[str], timeout: int = 30
) -> tuple[bool, str, str]:
    """
    Run a git command in the specified directory.

    Args:
        cwd: Working directory for the command
        args: Git command arguments (without 'git')
        timeout: Command timeout in seconds

    Returns:
        Tuple of (success, stdout, stderr)
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "Git command timed out"
    except FileNotFoundError:
        return False, "", "Git is not installed"
    except Exception as e:
        return False, "", str(e)


def is_git_repo(path: Path) -> bool:
    """Check if a path is inside a git repository."""
    success, _, _ = run_git_command(path, ["rev-parse", "--git-dir"])
    return success


def is_git_worktree(path: Path) -> bool:
    """Check if a path is a git worktree (not the main repo)."""
    if not is_git_repo(path):
        return False
    success, output, _ = run_git_command(path, ["rev-parse", "--is-inside-work-tree"])
    if not success or output != "true":
        return False
    # Check if it's the main worktree by comparing git-dir locations
    success, git_dir, _ = run_git_command(path, ["rev-parse", "--git-dir"])
    if not success:
        return False
    # Worktrees have a .git file (not directory) pointing to main repo
    git_path = path / ".git"
    return git_path.is_file()


def get_main_branch(project_path: Path) -> str:
    """Get the main branch name (main or master)."""
    success, output, _ = run_git_command(
        project_path, ["symbolic-ref", "refs/remotes/origin/HEAD"]
    )
    if success:
        # Output like "refs/remotes/origin/main"
        return output.split("/")[-1]

    # Check if main or master exists
    for branch in ["main", "master"]:
        success, _, _ = run_git_command(
            project_path, ["rev-parse", "--verify", branch]
        )
        if success:
            return branch

    # Default to main
    return "main"


class WorktreeManager:
    """
    Manages git worktrees for a single project.

    Provides create/delete/merge functionality for isolated agent work.
    """

    def __init__(self, project_name: str, project_dir: Path):
        """
        Initialize the worktree manager.

        Args:
            project_name: Name of the project
            project_dir: Path to the main project directory (git repo)
        """
        self.project_name = project_name
        self.project_dir = project_dir
        self._lock = threading.Lock()

    @property
    def worktree_path(self) -> Path:
        """Get the worktree directory path for this project."""
        return WORKTREE_BASE / self.project_name / WORKTREE_BRANCH_PREFIX

    @property
    def worktree_branch(self) -> str:
        """Get the worktree branch name for this project."""
        return f"{WORKTREE_BRANCH_PREFIX}-{self.project_name}"

    def exists(self) -> bool:
        """Check if the worktree exists."""
        return self.worktree_path.exists() and is_git_repo(self.worktree_path)

    def get_status(self) -> dict[str, Any]:
        """
        Get the current worktree status.

        Returns:
            Dictionary with worktree status information.
        """
        if not self.exists():
            return {
                "exists": False,
                "worktreePath": None,
                "branch": None,
                "commitsAhead": 0,
                "hasChanges": False,
                "mainBranch": get_main_branch(self.project_dir),
            }

        wt_path = self.worktree_path

        # Get current branch in worktree
        success, branch, _ = run_git_command(
            wt_path, ["rev-parse", "--abbrev-ref", "HEAD"]
        )
        if not success:
            branch = None

        # Get main branch
        main_branch = get_main_branch(self.project_dir)

        # Count commits ahead of main
        commits_ahead = 0
        if branch:
            success, output, _ = run_git_command(
                wt_path, ["rev-list", "--count", f"{main_branch}..HEAD"]
            )
            if success and output.isdigit():
                commits_ahead = int(output)

        # Check for uncommitted changes
        success, status_output, _ = run_git_command(wt_path, ["status", "--porcelain"])
        has_changes = bool(status_output.strip()) if success else False

        return {
            "exists": True,
            "worktreePath": str(wt_path),
            "branch": branch,
            "commitsAhead": commits_ahead,
            "hasChanges": has_changes,
            "mainBranch": main_branch,
        }

    def get_diff(self) -> dict[str, Any]:
        """
        Get the diff between worktree and main branch.

        Returns:
            Dictionary with diff information.
        """
        if not self.exists():
            return {
                "error": "Worktree does not exist",
                "files": [],
                "summary": None,
            }

        wt_path = self.worktree_path
        main_branch = get_main_branch(self.project_dir)

        # Get list of changed files
        success, output, _ = run_git_command(
            wt_path, ["diff", "--name-status", f"{main_branch}...HEAD"]
        )

        files = []
        if success and output:
            for line in output.split("\n"):
                if not line.strip():
                    continue
                parts = line.split("\t", 1)
                if len(parts) >= 2:
                    status = parts[0]
                    filename = parts[1]
                    status_map = {
                        "A": "added",
                        "M": "modified",
                        "D": "deleted",
                        "R": "renamed",
                    }
                    files.append({
                        "status": status_map.get(status[0], "unknown"),
                        "path": filename,
                    })

        # Get diff stat summary
        success, summary, _ = run_git_command(
            wt_path, ["diff", "--stat", f"{main_branch}...HEAD"]
        )

        return {
            "files": files,
            "summary": summary if success else None,
            "mainBranch": main_branch,
        }

    def create(self, from_branch: str | None = None) -> tuple[bool, str]:
        """
        Create a worktree for this project.

        Args:
            from_branch: Branch to create worktree from (defaults to main)

        Returns:
            Tuple of (success, message)
        """
        with self._lock:
            # Check if project is a git repo
            if not is_git_repo(self.project_dir):
                return False, "Project is not a git repository"

            # Check if worktree already exists
            if self.exists():
                return True, f"Worktree already exists at {self.worktree_path}"

            # Ensure base directory exists
            self.worktree_path.parent.mkdir(parents=True, exist_ok=True)

            # Determine base branch
            base_branch = from_branch or get_main_branch(self.project_dir)

            # Check for uncommitted changes in main repo
            success, status_output, _ = run_git_command(
                self.project_dir, ["status", "--porcelain"]
            )
            if success and status_output.strip():
                logger.warning(
                    "Main repo has uncommitted changes, stashing before creating worktree"
                )
                run_git_command(self.project_dir, ["stash", "push", "-m", "autocoder-pre-worktree"])

            # Check if branch already exists
            branch_name = self.worktree_branch
            success, _, _ = run_git_command(
                self.project_dir, ["rev-parse", "--verify", branch_name]
            )
            branch_exists = success

            if branch_exists:
                # Create worktree from existing branch
                success, output, error = run_git_command(
                    self.project_dir,
                    ["worktree", "add", str(self.worktree_path), branch_name],
                )
            else:
                # Create new branch and worktree
                success, output, error = run_git_command(
                    self.project_dir,
                    ["worktree", "add", "-b", branch_name, str(self.worktree_path), base_branch],
                )

            if not success:
                return False, f"Failed to create worktree: {error or output}"

            logger.info(f"Created worktree at {self.worktree_path} on branch {branch_name}")
            return True, f"Created worktree at {self.worktree_path}"

    def remove(self, force: bool = False) -> tuple[bool, str]:
        """
        Remove the worktree.

        Args:
            force: Force removal even with uncommitted changes

        Returns:
            Tuple of (success, message)
        """
        with self._lock:
            if not self.exists():
                return True, "Worktree does not exist"

            # Check for uncommitted changes if not forcing
            if not force:
                success, status_output, _ = run_git_command(
                    self.worktree_path, ["status", "--porcelain"]
                )
                if success and status_output.strip():
                    return False, "Worktree has uncommitted changes. Use force=True to discard."

            # Remove worktree using git command
            args = ["worktree", "remove"]
            if force:
                args.append("--force")
            args.append(str(self.worktree_path))

            success, output, error = run_git_command(self.project_dir, args)

            if not success:
                # Try force cleanup if normal removal fails
                if self.worktree_path.exists():
                    try:
                        shutil.rmtree(self.worktree_path)
                    except Exception as e:
                        return False, f"Failed to remove worktree: {error or output}. Cleanup error: {e}"
                # Also prune the worktree reference
                run_git_command(self.project_dir, ["worktree", "prune"])

            logger.info(f"Removed worktree at {self.worktree_path}")
            return True, "Worktree removed successfully"

    def merge_to_main(
        self, commit_message: str | None = None, delete_after: bool = True
    ) -> tuple[bool, str]:
        """
        Merge worktree changes back to main branch.

        Args:
            commit_message: Optional commit message for merge
            delete_after: Whether to delete worktree after successful merge

        Returns:
            Tuple of (success, message)
        """
        with self._lock:
            if not self.exists():
                return False, "Worktree does not exist"

            wt_path = self.worktree_path
            main_branch = get_main_branch(self.project_dir)

            # Check for uncommitted changes and commit them
            success, status_output, _ = run_git_command(wt_path, ["status", "--porcelain"])
            if success and status_output.strip():
                # Stage all changes
                run_git_command(wt_path, ["add", "-A"])
                # Commit with default message
                msg = commit_message or f"Autocoder work session - {datetime.now().isoformat()}"
                success, output, error = run_git_command(
                    wt_path, ["commit", "-m", msg]
                )
                if not success:
                    return False, f"Failed to commit changes: {error or output}"

            # Check if there are any commits to merge
            success, output, _ = run_git_command(
                wt_path, ["rev-list", "--count", f"{main_branch}..HEAD"]
            )
            if success and output == "0":
                return True, "No changes to merge"

            # Switch to main branch in project dir
            success, output, error = run_git_command(
                self.project_dir, ["checkout", main_branch]
            )
            if not success:
                return False, f"Failed to checkout {main_branch}: {error or output}"

            # Merge the worktree branch
            branch_name = self.worktree_branch
            success, output, error = run_git_command(
                self.project_dir, ["merge", branch_name, "--no-ff", "-m", f"Merge {branch_name}"]
            )

            if not success:
                # Check for merge conflicts
                if "conflict" in (error or output).lower():
                    return False, f"Merge conflicts detected. Resolve manually in {self.project_dir}"
                return False, f"Failed to merge: {error or output}"

            logger.info(f"Merged {branch_name} into {main_branch}")

            # Optionally delete worktree after merge
            if delete_after:
                self.remove(force=True)

            return True, f"Successfully merged {branch_name} into {main_branch}"

    def stage_changes(self) -> tuple[bool, str]:
        """
        Stage worktree changes in main project without committing.

        This allows the user to review changes before committing.

        Returns:
            Tuple of (success, message)
        """
        if not self.exists():
            return False, "Worktree does not exist"

        wt_path = self.worktree_path
        main_branch = get_main_branch(self.project_dir)

        # Commit any uncommitted changes in worktree
        success, status_output, _ = run_git_command(wt_path, ["status", "--porcelain"])
        if success and status_output.strip():
            run_git_command(wt_path, ["add", "-A"])
            run_git_command(
                wt_path, ["commit", "-m", f"Autocoder work - {datetime.now().isoformat()}"]
            )

        # Checkout main in project dir
        success, output, error = run_git_command(
            self.project_dir, ["checkout", main_branch]
        )
        if not success:
            return False, f"Failed to checkout {main_branch}: {error or output}"

        # Merge with --no-commit to stage changes
        branch_name = self.worktree_branch
        success, output, error = run_git_command(
            self.project_dir, ["merge", branch_name, "--no-commit", "--no-ff"]
        )

        if not success:
            if "conflict" in (error or output).lower():
                return False, "Merge conflicts detected. Resolve manually."
            # Check if already up to date
            if "already up to date" in (output or "").lower():
                return True, "Already up to date with worktree"
            return False, f"Failed to stage changes: {error or output}"

        return True, f"Changes from {branch_name} staged for review. Use 'git commit' to finalize."

    def discard(self) -> tuple[bool, str]:
        """
        Discard all worktree changes and remove the worktree.

        Returns:
            Tuple of (success, message)
        """
        with self._lock:
            if not self.exists():
                return True, "Nothing to discard"

            # Force remove the worktree
            success, msg = self.remove(force=True)
            if not success:
                return False, msg

            # Delete the branch
            branch_name = self.worktree_branch
            run_git_command(self.project_dir, ["branch", "-D", branch_name])

            return True, "Worktree and branch discarded"


# Global manager cache
_managers: dict[str, WorktreeManager] = {}
_managers_lock = threading.Lock()


def get_worktree_manager(project_name: str, project_dir: Path) -> WorktreeManager:
    """
    Get or create a WorktreeManager for a project.

    Args:
        project_name: Name of the project
        project_dir: Path to the project directory

    Returns:
        WorktreeManager instance
    """
    with _managers_lock:
        key = project_name
        if key not in _managers:
            _managers[key] = WorktreeManager(project_name, project_dir)
        return _managers[key]


def cleanup_manager(project_name: str) -> None:
    """Remove a manager from the cache."""
    with _managers_lock:
        _managers.pop(project_name, None)
