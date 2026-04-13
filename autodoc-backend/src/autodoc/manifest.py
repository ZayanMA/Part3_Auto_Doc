from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RepoManifest:
    repo_root: str
    total_files: int
    total_units: int
    unit_kind_counts: dict[str, int]
    readme_excerpt: str  # first 300 chars of README


def build_repo_manifest(
    repo: Path,
    units: list,
    all_files: list[str],
) -> RepoManifest:
    kind_counts: dict[str, int] = dict(Counter(u.kind for u in units))

    readme_excerpt = ""
    for name in ("README.md", "README.rst", "README.txt", "readme.md"):
        p = repo / name
        if p.exists() and p.is_file():
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
                readme_excerpt = text[:300].strip()
            except Exception:
                pass
            break

    return RepoManifest(
        repo_root=str(repo),
        total_files=len(all_files),
        total_units=len(units),
        unit_kind_counts=kind_counts,
        readme_excerpt=readme_excerpt,
    )


def render_manifest(m: RepoManifest) -> str:
    kind_lines = "\n".join(
        f"  - {kind}: {count}" for kind, count in sorted(m.unit_kind_counts.items())
    )
    lines = [
        f"Repository: {Path(m.repo_root).name}",
        f"Total source files: {m.total_files}",
        f"Total documentation units: {m.total_units}",
        "Unit breakdown by kind:",
        kind_lines,
    ]
    if m.readme_excerpt:
        lines.append(f"\nRepository purpose (from README):\n{m.readme_excerpt}")
    return "\n".join(lines)
