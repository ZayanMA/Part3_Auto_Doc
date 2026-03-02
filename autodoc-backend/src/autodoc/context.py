from __future__ import annotations

from pathlib import Path

from autodoc.git_utils import get_file_diff, read_file_at_head
from autodoc.models import ContextBundle


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