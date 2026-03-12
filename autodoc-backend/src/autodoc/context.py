from __future__ import annotations

from pathlib import Path

from autodoc.git_utils import get_file_diff, read_file_at_head
from autodoc.models import ContextBundle
from collections import defaultdict
from autodoc.models import DocumentationUnit, UnitContextBundle

IGNORED_DIRS = {
    ".git", ".autodoc", "__pycache__", ".venv", "venv",
    "node_modules", "dist", "build", ".next", "coverage",
    ".github", ".devcontainer"
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
    
    # special-case "src/<pkg>" as a strong module boundary
    if len(parts) >= 2 and parts[0] == "src":
        return str(Path(parts[0]) / parts[1])
    
    # top-level files -> "root"
    if len(parts) == 1:
        return "root"

    # otherwise return first two parts
    
    return str(Path(parts[0]) / parts[1])
    

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

def title_from_group_key(group_key: str) -> str:
    last = Path(group_key).name
    return last.replace("_", " ").replace("-", " ").title()

def slug_from_group_key(group_key: str) -> str:
    # stable filename-safe slug
    return group_key.replace("/", "__").replace("\\", "__")

def make_units_from_groups(groups: dict[str, list[str]]) -> list[DocumentationUnit]:
    units: list[DocumentationUnit] = []
    for root, files in sorted(groups.items(), key=lambda kv: kv[0]):
        units.append(
            DocumentationUnit(
                name=title_from_group_key(root),
                slug=slug_from_group_key(root),
                kind="module",
                root=root,
                files=sorted(files),
            )
        )
    return units

def build_unit_context_bundle(
    repo: Path,
    base: str,
    head: str,
    unit: DocumentationUnit,
    include_diff: bool = True,
    max_file_chars: int = 6000,
    max_files_fulltext: int = 8,
    ) -> UnitContextBundle:
    readme_context = _read_readme_if_present(repo)

    # Read contents for all files (but we may truncate / limit)
    raw_contents: list[tuple[str, str]] = []
    diffs: list[tuple[str, str]] = []

    for file_path in unit.files:
        full_path = repo / file_path
        if full_path.exists():
            content = _read_text_file(full_path)
        else:
            content = read_file_at_head(repo, head, file_path)
        
        # Truncate big files to keep prompts bounded

        if len(content) > max_file_chars:
            content = content[:max_file_chars] + "\n\n...[truncated]...\n"

        raw_contents.append((file_path, content))

        if include_diff:
            diff_text = get_file_diff(repo, base, head, file_path)
            if diff_text.strip():
                diffs.append((file_path, diff_text))

    # Supress tiny/helper files from being "front and centre"
    # Keep them available, but we'll push them to the end and possibly limit full-text inclusion.
    def sort_key(item: tuple[str, str]) -> tuple[int, int]:
        path, content = item
        helper = looks_like_helper_file(path, content)
        # non-helper first, then longer files first
        return (1 if helper else 0, -len(content))

    sorted_contents = sorted(raw_contents, key=sort_key)

    included_contents = sorted_contents[:max_files_fulltext]

    return UnitContextBundle(
        unit_name=unit.name,
        unit_slug=unit.slug,
        unit_kind=unit.kind,
        unit_root=unit.root,
        readme_content=readme_context,
        files=unit.files,
        file_contents=included_contents,
        diffs=diffs,
    )