from __future__ import annotations

from pathlib import Path

from autodoc.git_utils import get_file_diff, read_file_at_head
from autodoc.models import ContextBundle
from collections import defaultdict

IGNORED_DIRS = {
    ".git", ".autodoc", "__pycache__", ".venv", "venv",
    "node_modules", "dist", "build", ".next", "coverage"
}

IGNORED_FILE_NAMES = {
    "__init__.py", "__main__.py"
}

HELPER_NAME_HINTS = {
    "util", "utils", "helper", "helpers", "common", "shared", "base", "types", "constants"
}



def _read_text_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(errors="ignore")


def _read_readme_if_present(repo: Path) -> str:
    for name in ("README.md", "README.rst", "README.txt", "readme.md"):
        p = repo / name
        if p.exists() and p.is_file():
            return _read_text_file(p)
    return ""


def read_repo_readme(repo: Path) -> str:
    return _read_readme_if_present(repo)


def _get_nearby_files(repo: Path, target_file: str, max_files: int = 3) -> tuple[list[str], list[str]]:
    target = Path(target_file)
    folder = repo / target.parent
    if not folder.exists() or not folder.is_dir():
        return [], []

    file_names: list[str] = []
    contents: list[str] = []

    for child in sorted(folder.iterdir()):
        if child.is_dir():
            continue
        if child.name == target.name:
            continue

        try:
            text = _read_text_file(child)
        except Exception:
            continue

        rel = str(child.relative_to(repo))
        file_names.append(rel)
        contents.append(text)

        if len(file_names) >= max_files:
            break

    return file_names, contents


def build_context_bundle(
    repo: Path,
    base: str,
    head: str,
    file_path: str,
    include_diff: bool = True,
) -> ContextBundle:
    full_path = repo / file_path

    if full_path.exists():
        target_content = _read_text_file(full_path)
    else:
        target_content = read_file_at_head(repo, head, file_path)

    diff_text = get_file_diff(repo, base, head, file_path) if include_diff else ""
    readme_content = _read_readme_if_present(repo)
    nearby_files, nearby_contents = _get_nearby_files(repo, file_path)

    return ContextBundle(
        target_file=file_path,
        target_content=target_content,
        diff_text=diff_text,
        readme_content=readme_content,
        nearby_files=nearby_files,
        nearby_contents=nearby_contents,
    )


def is_ignored_path(path: str) -> bool:
    parts = Path(path).parts
    return any(part in IGNORED_DIRS for part in parts)


def group_key_for_file(path: str) -> str:
    p = Path(path)
    parts = p.parts

    # Example strategy:
    # src/auth/login.py      -> src/auth
    # src/api/routes/user.py -> src/api
    # auth/session.py        -> auth
    if len(parts) >= 2:
        return str(Path(parts[0]) / parts[1])
    elif len(parts) == 1:
        return parts[0]
    return ""
    

def group_files_into_units(paths: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = defaultdict(list)

    for path in paths:
        if is_ignored_path(path):
            continue

        key = group_key_for_file(path)
        if not key:
            continue

        groups[key].append(path)

    return dict(groups)


def looks_like_helper_file(path: str, content: str) -> bool:
    name = Path(path).stem.lower()

    if name in HELPER_NAME_HINTS:
        return True

    if any(hint in name for hint in HELPER_NAME_HINTS):
        return True

    # crude size heuristic
    line_count = len(content.splitlines())
    if line_count < 20:
        return True

    return False

def parent_group_key(group_key: str) -> str | None:
    p = Path(group_key)
    if len(p.parts) <= 1:
        return None
    return str(Path(*p.parts[:-1]))


def merge_small_groups(
    groups: dict[str, list[str]],
    min_files: int = 3,
) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = defaultdict(list)

    for key, files in groups.items():
        if len(files) >= min_files:
            merged[key].extend(files)
        else:
            parent = parent_group_key(key)
            merged[parent or key].extend(files)

    return dict(merged)