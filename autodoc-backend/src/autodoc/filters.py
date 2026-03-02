from __future__ import annotations

from pathlib import Path
from autodoc.models import ChangedFile

TEXT_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".c", ".cpp",
    ".h", ".hpp", ".cs", ".php", ".rb", ".swift", ".kt", ".kts", ".scala",
    ".lua", ".r", ".m", ".mm", ".sql", ".sh", ".bash", ".zsh", ".ps1",
    ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg", ".md", ".rst", ".txt",
    ".html", ".css", ".scss", ".xml",
}

EXCLUDED_DIR_NAMES = {
    ".git", ".hg", ".svn", ".venv", "venv", "__pycache__", "node_modules",
    "dist", "build", ".next", ".nuxt", ".cache", ".mypy_cache", ".pytest_cache",
    "coverage", ".idea", ".vscode", "target", "out", "bin", "obj", ".autodoc",
}

EXCLUDED_FILENAMES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "poetry.lock",
    "Cargo.lock",
}


def is_probably_text_file(file_path: str) -> bool:
    path = Path(file_path)

    if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
        return False

    if path.name in EXCLUDED_FILENAMES:
        return False

    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True

    if path.suffix == "" and path.name in {"Dockerfile", "Makefile"}:
        return True

    return False


def get_all_relevant_files(repo: Path) -> list[ChangedFile]:
    results: list[ChangedFile] = []

    for path in repo.rglob("*"):
        if not path.is_file():
            continue

        rel_path = str(path.relative_to(repo))

        if is_probably_text_file(rel_path):
            results.append(ChangedFile(path=rel_path, status="A"))

    return results