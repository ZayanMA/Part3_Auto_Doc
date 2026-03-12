from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from autodoc.cache import AUTODOC_DIR
from autodoc.models import DocumentationUnit


INDEX_FILENAME = "index.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha1_text(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()


def read_text_best_effort(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(errors="ignore")


@dataclass
class FileInfo:
    path: str
    sha1: str
    unit_root: str
    imports: List[str]  # module strings (best effort)


@dataclass
class UnitInfo:
    root: str
    slug: str
    title: str
    kind: str
    files: List[str]


@dataclass
class RepoIndex:
    schema_version: int
    repo_root: str
    created_at_utc: str
    updated_at_utc: str
    units: Dict[str, UnitInfo]  # key = unit_root
    files: Dict[str, FileInfo]  # key = file path
    # file-level dependency graph (resolved to file paths)
    deps: Dict[str, List[str]]  # key=file_path -> list[file_path] it depends on

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)

    @staticmethod
    def from_json(s: str) -> "RepoIndex":
        raw = json.loads(s)
        units = {k: UnitInfo(**v) for k, v in raw["units"].items()}
        files = {k: FileInfo(**v) for k, v in raw["files"].items()}
        return RepoIndex(
            schema_version=raw["schema_version"],
            repo_root=raw["repo_root"],
            created_at_utc=raw["created_at_utc"],
            updated_at_utc=raw["updated_at_utc"],
            units=units,
            files=files,
            deps=raw.get("deps", {}),
        )


def index_path(repo: Path) -> Path:
    return repo / AUTODOC_DIR / INDEX_FILENAME


def load_index(repo: Path) -> Optional[RepoIndex]:
    p = index_path(repo)
    if not p.exists():
        return None
    try:
        return RepoIndex.from_json(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_index(repo: Path, idx: RepoIndex) -> None:
    p = index_path(repo)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(idx.to_json(), encoding="utf-8")


# -------------------------
# Python import extraction
# -------------------------

def _parse_python_imports(source: str) -> List[str]:
    """
    Return raw module names (best effort):
    - import x.y -> "x.y"
    - from x.y import z -> "x.y"
    - from . import a -> "." (we'll resolve relative later if possible)
    """
    imports: List[str] = []
    try:
        tree = ast.parse(source)
    except Exception:
        return imports

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            level = getattr(node, "level", 0) or 0
            if level > 0:
                # encode relative level as leading dots, e.g. "..utils"
                imports.append("." * level + mod)
            else:
                if mod:
                    imports.append(mod)

    # de-dupe while preserving order
    seen = set()
    out = []
    for x in imports:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


def _python_module_name_for_file(repo: Path, rel_path: str) -> Optional[str]:
    """
    Best-effort module name:
    - handles src/<pkg>/... as <pkg>....
    - ignores non-.py
    """
    p = Path(rel_path)
    if p.suffix != ".py":
        return None

    parts = p.parts

    # If file is under src/, treat src as module root
    if len(parts) >= 2 and parts[0] == "src":
        mod_parts = list(parts[1:])
    else:
        mod_parts = list(parts)

    if mod_parts[-1] == "__init__.py":
        mod_parts = mod_parts[:-1]
    else:
        mod_parts[-1] = mod_parts[-1].replace(".py", "")

    if not mod_parts:
        return None

    return ".".join(mod_parts)


def _resolve_relative_import(current_module: str, import_str: str) -> Optional[str]:
    """
    Resolve something like:
      current_module = "pkg.sub.mod"
      import_str = "..utils"
    -> "pkg.utils" (best effort)
    """
    if not import_str.startswith("."):
        return import_str

    # count leading dots
    i = 0
    while i < len(import_str) and import_str[i] == ".":
        i += 1

    level = i
    remainder = import_str[i:]  # may be ""
    cur_parts = current_module.split(".")
    if level > len(cur_parts):
        return None

    base_parts = cur_parts[: len(cur_parts) - level]
    if remainder:
        base_parts += remainder.split(".")
    if not base_parts:
        return None
    return ".".join(base_parts)


def build_import_graph(repo: Path, all_files: List[str]) -> Tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    """
    Returns:
      - raw_imports_by_file: file -> list[str module imports]
      - resolved_deps_by_file: file -> list[file paths] (only within repo, best effort)
    """
    module_to_file: Dict[str, str] = {}
    file_to_module: Dict[str, str] = {}

    for f in all_files:
        mod = _python_module_name_for_file(repo, f)
        if mod:
            module_to_file[mod] = f
            file_to_module[f] = mod

    raw_imports_by_file: Dict[str, List[str]] = {}
    resolved: Dict[str, List[str]] = {}

    for f in all_files:
        p = repo / f
        if p.suffix != ".py" or not p.exists():
            raw_imports_by_file[f] = []
            resolved[f] = []
            continue

        src = read_text_best_effort(p)
        raw = _parse_python_imports(src)
        raw_imports_by_file[f] = raw

        cur_mod = file_to_module.get(f, "")
        deps: List[str] = []

        for imp in raw:
            imp_mod = _resolve_relative_import(cur_mod, imp) if cur_mod else imp
            if not imp_mod:
                continue

            # Try progressively shorter prefixes: a.b.c -> a.b.c, a.b, a
            cand = imp_mod
            while cand:
                if cand in module_to_file:
                    deps.append(module_to_file[cand])
                    break
                if "." not in cand:
                    break
                cand = cand.rsplit(".", 1)[0]

        # de-dupe
        seen = set()
        out = []
        for d in deps:
            if d not in seen:
                out.append(d)
                seen.add(d)
        resolved[f] = out

    return raw_imports_by_file, resolved


# -------------------------
# Build/refresh index
# -------------------------

def build_repo_index(
    repo: Path,
    units: List[DocumentationUnit],
    all_files: List[str],
) -> RepoIndex:
    now = utc_now_iso()

    # Build unit info
    units_map: Dict[str, UnitInfo] = {}
    file_unit_root: Dict[str, str] = {}

    for u in units:
        units_map[u.root] = UnitInfo(
            root=u.root,
            slug=u.slug,
            title=u.name,
            kind=u.kind,
            files=sorted(u.files),
        )
        for f in u.files:
            file_unit_root[f] = u.root

    raw_imports, deps = build_import_graph(repo, all_files)

    files_map: Dict[str, FileInfo] = {}
    for f in all_files:
        p = repo / f
        if p.exists() and p.is_file():
            content = read_text_best_effort(p) if p.suffix in {".py", ".md", ".toml", ".json", ".yaml", ".yml", ".txt"} else read_text_best_effort(p)
            h = sha1_text(content)
        else:
            h = "missing"

        files_map[f] = FileInfo(
            path=f,
            sha1=h,
            unit_root=file_unit_root.get(f, "unassigned"),
            imports=raw_imports.get(f, []),
        )

    return RepoIndex(
        schema_version=1,
        repo_root=str(repo),
        created_at_utc=now,
        updated_at_utc=now,
        units=units_map,
        files=files_map,
        deps=deps,
    )


def diff_indices(old: Optional[RepoIndex], new: RepoIndex) -> dict:
    """
    Return a summary of structural changes.
    """
    if old is None:
        return {"first_run": True, "added_units": list(new.units.keys()), "removed_units": [], "changed_units": []}

    old_units = set(old.units.keys())
    new_units = set(new.units.keys())

    added_units = sorted(list(new_units - old_units))
    removed_units = sorted(list(old_units - new_units))

    changed_units: List[str] = []
    for u in sorted(list(old_units & new_units)):
        if set(old.units[u].files) != set(new.units[u].files):
            changed_units.append(u)

    return {
        "first_run": False,
        "added_units": added_units,
        "removed_units": removed_units,
        "changed_units": changed_units,
    }


def impacted_units(
    idx: RepoIndex,
    changed_files: Set[str],
    depth: int = 2,
) -> Set[str]:
    """
    Returns unit roots that are impacted by changed files:
      - units containing changed files
      - units depending on changed files (reverse deps), BFS up to `depth`
    """
    # Direct: unit that owns the changed file
    impacted_files: Set[str] = set(changed_files)

    # Build reverse dep graph: dep -> [users]
    rev: Dict[str, List[str]] = {}
    for src, deps in idx.deps.items():
        for d in deps:
            rev.setdefault(d, []).append(src)

    # BFS reverse dependencies
    frontier = list(changed_files)
    seen = set(changed_files)

    for _ in range(depth):
        nxt: List[str] = []
        for f in frontier:
            for user in rev.get(f, []):
                if user not in seen:
                    seen.add(user)
                    nxt.append(user)
                    impacted_files.add(user)
        frontier = nxt
        if not frontier:
            break

    impacted_unit_roots: Set[str] = set()
    for f in impacted_files:
        finfo = idx.files.get(f)
        if finfo:
            impacted_unit_roots.add(finfo.unit_root)

    # Drop unassigned if any
    impacted_unit_roots.discard("unassigned")
    return impacted_unit_roots