from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List

from autodoc.models import ChangedFile


class GitCommandError(RuntimeError):
    """Raised when a Git command exits with a non-zero status."""


def _run_git(repo: Path, args: list[str]) -> str:
    """
    Execute a Git command against the given repository path.

    The command is run using `git -C <repo>` so the current Python working
    directory does not need to be changed.

    Args:
        repo: Path to the target Git repository.
        args: Git command arguments, excluding the leading `git`.

    Returns:
        The command standard output as text.

    Raises:
        GitCommandError: If the Git command exits with a non-zero status.
    """
    cmd = ["git", "-C", str(repo), *args]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )

    # Convert Git failures into a domain-specific exception so callers do not
    # need to handle raw subprocess errors or inspect return codes themselves.
    if result.returncode != 0:
        raise GitCommandError(result.stderr.strip() or "Git command failed")

    return result.stdout


def ensure_git_repo(repo: Path) -> None:
    """
    Validate that the supplied path is inside a Git working tree.

    This function is intended as a lightweight repository precondition check
    before performing other Git operations.

    Args:
        repo: Path expected to point to a Git repository or a directory within one.

    Raises:
        GitCommandError: If the path is not inside a valid Git working tree.
    """
    _run_git(repo, ["rev-parse", "--is-inside-work-tree"]) # Checks if we are in a Git
                                                           # working tree


def get_changed_files(repo: Path, base: str, head: str) -> List[ChangedFile]:
    """
    Retrieve files changed between two Git refs.

    Uses `git diff --name-status` so both the file path and change type
    (for example added, modified, deleted, renamed) are preserved.

    Args:
        repo: Path to the Git repository.
        base: Base Git ref for the comparison.
        head: Head Git ref for the comparison.

    Returns:
        A list of `ChangedFile` objects representing each changed file and its status.

    Notes:
        Rename entries from Git may include a similarity score such as `R100`.
        In those cases, the destination path is used and the status is normalised
        to `R`.
    """
    output = _run_git(repo, ["diff", "--name-status", base, head])
    changed: list[ChangedFile] = []

    for line in output.splitlines():
        if not line.strip():
            continue

        parts = line.split("\t")
        status = parts[0]

        # Rename entries typically appear as:
        #   R100    old/path.py    new/path.py
        # We store the new path because that is the effective path at `head`.
        if status.startswith("R") and len(parts) >= 3:
            path = parts[2]
            changed.append(ChangedFile(path=path, status="R"))
        elif len(parts) >= 2:
            path = parts[1]
            changed.append(ChangedFile(path=path, status=status))

    return changed


def get_file_diff(repo: Path, base: str, head: str, file_path: str) -> str:
    """
    Return the unified diff for a single file between two Git refs.

    Args:
        repo: Path to the Git repository.
        base: Base Git ref for the comparison.
        head: Head Git ref for the comparison.
        file_path: Repository-relative path of the file to diff.

    Returns:
        The textual diff for the requested file.
    """
    return _run_git(repo, ["diff", base, head, "--", file_path])


def read_file_at_head(repo: Path, head: str, file_path: str) -> str:
    """
    Read a file exactly as it exists at a specific Git ref.

    This is useful when generating documentation from the target revision
    rather than from the local filesystem state.

    Args:
        repo: Path to the Git repository.
        head: Git ref, branch, tag, or commit hash to read from.
        file_path: Repository-relative path of the file to read.

    Returns:
        The file contents at the specified Git ref.

    Raises:
        GitCommandError: If the ref or file cannot be resolved by Git.
    """
    return _run_git(repo, ["show", f"{head}:{file_path}"])