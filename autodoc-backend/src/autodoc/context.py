from __future__ import annotations

from pathlib import Path
import re
import subprocess

from autodoc.git_utils import get_file_diff, read_file_at_head
from autodoc.models import ContextBundle
from collections import defaultdict
from autodoc.models import DocumentationUnit, UnitContextBundle
from autodoc.cache import AUTODOC_DIR

IGNORED_DIRS = {
    ".git", ".autodoc", "__pycache__", ".venv", "venv",
    "node_modules", "dist", "build", ".next", "coverage",
    ".github", ".devcontainer"
}

IGNORED_FILE_NAMES = {
    "__init__.py", "__main__.py"
}

_DATA_ONLY_EXTENSIONS = {'.json', '.po', '.pot', '.csv', '.xliff', '.strings', '.yaml', '.yml', '.mo'}
_DATA_DIR_NAMES = {'locales', 'i18n', 'translations', 'lang', 'locale', 'nls'}
_ISO_LANG_CODES = {
    'en', 'ar', 'ja', 'fr', 'de', 'zh', 'ko', 'es', 'pt', 'it', 'ru', 'nl',
    'sv', 'pl', 'tr', 'uk', 'he', 'fi', 'da', 'nb', 'cs', 'hu', 'ro', 'sk',
    'bg', 'hr', 'lt', 'lv', 'sl', 'et', 'vi', 'th', 'id', 'ms', 'fa', 'ca',
}

HELPER_NAME_HINTS = {
    "util", "utils", "helper", "helpers", "common", "shared", "base", "types", "constants"
}

KIND_PRIMARY_PATTERNS = {
    "api": {"router", "route", "endpoint", "view", "handler"},
    "models": {"model", "schema", "entity", "orm"},
    "config": {"config", "settings", "conf", "env"},
    "cli": {"cli", "command", "cmd", "main"},
    "tests": {"test", "spec", "fixture"},
}


def _read_existing_unit_doc(repo: Path, unit_slug: str) -> str:
    p = repo / AUTODOC_DIR / "units" / f"{unit_slug}.md"
    if p.exists() and p.is_file():
        return _read_text_file(p)
    return ""


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

    if len(parts) >= 2 and parts[0] == "src":
        return str(Path(parts[0]) / parts[1])

    if len(parts) == 1:
        return "root"

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

    line_count = len(content.splitlines())
    if line_count < 20:
        return True

    return False


def detect_unit_kind(files: list[str]) -> str:
    """Detect the semantic kind of a unit from its file names."""
    names = {Path(f).stem.lower() for f in files}

    # Check if majority look like tests
    test_count = sum(1 for n in names if "test" in n or "spec" in n)
    if test_count > len(names) / 2:
        return "tests"

    for kind, patterns in KIND_PRIMARY_PATTERNS.items():
        if any(pattern in name for name in names for pattern in patterns):
            return kind

    return "module"


def apply_unit_overrides(
    groups: dict[str, list[str]],
    overrides: dict[str, list[str]],
    all_paths: list[str],
) -> dict[str, list[str]]:
    """Move files matching configured path prefixes into named override groups."""
    if not overrides:
        return groups

    result: dict[str, list[str]] = dict(groups)

    for group_name, prefixes in overrides.items():
        override_files: list[str] = []
        # Collect files matching any prefix
        for path in all_paths:
            if any(path.startswith(prefix) for prefix in prefixes):
                override_files.append(path)

        if not override_files:
            continue

        # Remove these files from existing groups
        paths_to_move = set(override_files)
        new_result: dict[str, list[str]] = {}
        for key, files in result.items():
            remaining = [f for f in files if f not in paths_to_move]
            if remaining:
                new_result[key] = remaining

        new_result[group_name] = override_files
        result = new_result

    return result


def merge_by_import_coupling(
    groups: dict[str, list[str]],
    deps: dict[str, set[str]],
    threshold: float = 0.5,
) -> dict[str, list[str]]:
    """Merge groups that have strong import coupling. Runs max 3 passes."""
    if not deps:
        return groups

    def coupling(g1_files: list[str], g2_files: list[str]) -> float:
        g2_set = set(g2_files)
        imports_into_g2 = sum(
            1 for f in g1_files
            for dep in deps.get(f, set())
            if dep in g2_set
        )
        total_imports = sum(len(deps.get(f, set())) for f in g1_files)
        if total_imports == 0:
            return 0.0
        return imports_into_g2 / total_imports

    current = dict(groups)
    for _ in range(3):
        keys = list(current.keys())
        merged_into: dict[str, str] = {}

        for i, k1 in enumerate(keys):
            for k2 in keys[i + 1:]:
                if k1 in merged_into or k2 in merged_into:
                    continue
                c = max(
                    coupling(current[k1], current.get(k2, [])),
                    coupling(current.get(k2, []), current[k1]),
                )
                if c > threshold:
                    merged_into[k2] = k1

        if not merged_into:
            break

        new: dict[str, list[str]] = {}
        for key, files in current.items():
            target = merged_into.get(key, key)
            new.setdefault(target, []).extend(files)
        current = new

    return current


def parent_group_key(group_key: str) -> str | None:
    p = Path(group_key)
    if len(p.parts) <= 1:
        return None
    return str(Path(*p.parts[:-1]))


def collapse_homogeneous_siblings(groups: dict[str, list[str]]) -> dict[str, list[str]]:
    """Merge locale/variant sibling groups into one parent, or drop if pure data dirs."""
    parent_to_children: dict[str, list[str]] = defaultdict(list)
    for key in groups:
        p = parent_group_key(key)
        if p is not None:
            parent_to_children[p].append(key)

    result = dict(groups)

    for parent, children in parent_to_children.items():
        if len(children) < 2:
            continue

        # Compute filename overlap across sibling groups
        sibling_file_sets = [{Path(f).name for f in result[child]} for child in children if child in result]
        if len(sibling_file_sets) < 2:
            continue

        is_homogeneous = False
        for i in range(len(sibling_file_sets)):
            for j in range(i + 1, len(sibling_file_sets)):
                a, b = sibling_file_sets[i], sibling_file_sets[j]
                if not a or not b:
                    continue
                overlap = len(a & b) / min(len(a), len(b))
                if overlap >= 0.6:
                    is_homogeneous = True
                    break
            if is_homogeneous:
                break

        if not is_homogeneous:
            continue

        # Merge all siblings into parent
        merged_files: list[str] = []
        for child in children:
            if child in result:
                merged_files.extend(result.pop(child))

        parent_dir_name = Path(parent).name.lower()
        all_data_ext = all(Path(f).suffix.lower() in _DATA_ONLY_EXTENSIONS for f in merged_files)
        if all_data_ext and parent_dir_name in _DATA_DIR_NAMES:
            # Drop entirely — pure locale data, not worth documenting
            continue

        existing = result.get(parent, [])
        result[parent] = existing + merged_files

    return result


def enrich_unit_names(
    units: list["DocumentationUnit"],
    repo_path: "Path",
    fast_model: str,
) -> list["DocumentationUnit"]:
    """Use a batched LLM call to give units descriptive names. Falls back to heuristics on error."""
    import hashlib
    import json
    import logging

    from autodoc.cache import AUTODOC_DIR as _AUTODOC_DIR
    from autodoc.llm import call_llm_json
    from autodoc.prompts import UNIT_NAMING_PROMPT

    log = logging.getLogger(__name__)
    cache_path = repo_path / _AUTODOC_DIR / "name_cache.json"
    cache: dict[str, dict] = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    def _cache_key(unit: "DocumentationUnit") -> str:
        combo = unit.slug + ":" + ",".join(sorted(unit.files))
        return hashlib.md5(combo.encode()).hexdigest()[:10]

    def _code_snippet(unit: "DocumentationUnit") -> str:
        """Return up to 5 lines from the largest non-test file."""
        best_path: str | None = None
        best_size = 0
        for f in unit.files[:12]:
            if "test" in Path(f).stem.lower():
                continue
            full = repo_path / f
            if full.exists():
                size = full.stat().st_size
                if size > best_size:
                    best_size = size
                    best_path = f
        if best_path:
            try:
                lines = (repo_path / best_path).read_text(encoding="utf-8", errors="ignore").splitlines()
                return "\n".join(lines[:5])
            except Exception:
                pass
        return ""

    # Separate units needing LLM naming from cached ones
    uncached: list["DocumentationUnit"] = []
    for unit in units:
        key = _cache_key(unit)
        if key not in cache:
            uncached.append(unit)

    if uncached:
        try:
            # Build XML-style unit list for the prompt
            parts: list[str] = []
            for unit in uncached:
                files_sample = unit.files[:12]
                snippet = _code_snippet(unit)
                parts.append(
                    f'<unit slug="{unit.slug}">\n'
                    f'  <files>{", ".join(files_sample)}</files>\n'
                    f'  <snippet>{snippet}</snippet>\n'
                    f'</unit>'
                )
            unit_xml_list = "\n".join(parts)
            # Use str.replace, NOT .format() — the template contains literal { } in
            # the JSON example which would cause KeyError with Python's str.format().
            prompt = UNIT_NAMING_PROMPT.replace("{unit_xml_list}", unit_xml_list)

            result = call_llm_json(prompt, fast_model)
            if isinstance(result, dict):
                for unit in uncached:
                    key = _cache_key(unit)
                    entry = result.get(unit.slug)
                    if isinstance(entry, dict) and "name" in entry:
                        cache[key] = {
                            "name": entry["name"],
                            "coherent": bool(entry.get("coherent", True)),
                        }

            try:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
            except Exception:
                pass
        except Exception as e:
            log.warning("enrich_unit_names failed, using heuristic names: %s", e)

    # Apply cached names back to units
    result_units: list["DocumentationUnit"] = []
    for unit in units:
        key = _cache_key(unit)
        entry = cache.get(key)
        if entry and entry.get("name"):
            if not entry.get("coherent", True):
                log.info("Unit '%s' flagged as incoherent by LLM", unit.slug)
            from dataclasses import replace
            updated = replace(unit, name=entry["name"], name_source="llm")
            result_units.append(updated)
        else:
            result_units.append(unit)

    return result_units


def verify_units_relevance(
    units: list["DocumentationUnit"],
    repo_path: "Path",
    fast_model: str,
) -> list["DocumentationUnit"]:
    """Filter borderline units (locale dirs, data-only) using a cheap LLM check."""
    import hashlib
    import json
    import logging

    from autodoc.cache import AUTODOC_DIR as _AUTODOC_DIR
    from autodoc.llm import generate_documentation

    log = logging.getLogger(__name__)
    cache_path = repo_path / _AUTODOC_DIR / "relevance_cache.json"
    cache: dict[str, bool] = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except Exception:
            cache = {}

    def _is_borderline(unit: "DocumentationUnit") -> bool:
        parts = Path(unit.root).parts
        top_dir = parts[0].lower() if parts else unit.root.lower()
        if top_dir in _ISO_LANG_CODES:
            return True
        if unit.files and all(Path(f).suffix.lower() in _DATA_ONLY_EXTENSIONS for f in unit.files):
            return True
        return False

    def _cache_key(unit: "DocumentationUnit") -> str:
        files_hash = hashlib.md5(",".join(sorted(unit.files)).encode()).hexdigest()[:8]
        return f"{unit.slug}:{files_hash}"

    kept: list["DocumentationUnit"] = []
    cache_updated = False

    for unit in units:
        if not _is_borderline(unit):
            kept.append(unit)
            continue

        key = _cache_key(unit)
        if key in cache:
            if cache[key]:
                kept.append(unit)
            else:
                log.info("Skipping unit '%s' (cached: not relevant)", unit.name)
            continue

        files_sample = unit.files[:10]
        prompt = (
            f"Unit: `{unit.name}`. Files: `{files_sample}`. "
            "Does this contain source code or business logic worth documenting? "
            "Answer YES or NO only."
        )
        try:
            answer, _ = generate_documentation(prompt, unit.slug, model=fast_model)
            is_relevant = answer.strip().upper().startswith("YES")
        except Exception:
            is_relevant = True  # default to keeping on error

        cache[key] = is_relevant
        cache_updated = True

        if is_relevant:
            kept.append(unit)
        else:
            log.info("Skipping unit '%s' (LLM: not relevant)", unit.name)

    if cache_updated:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache, indent=2), encoding="utf-8")
        except Exception:
            pass

    return kept


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
    if last == "root":
        return "Repository Root"
    return last.replace("_", " ").replace("-", " ").title()


def slug_from_group_key(group_key: str) -> str:
    return group_key.replace("/", "__").replace("\\", "__")


def make_units_from_groups(groups: dict[str, list[str]]) -> list[DocumentationUnit]:
    units: list[DocumentationUnit] = []
    for root, files in sorted(groups.items(), key=lambda kv: kv[0]):
        units.append(
            DocumentationUnit(
                name=title_from_group_key(root),
                slug=slug_from_group_key(root),
                kind=detect_unit_kind(files),
                root=root,
                files=sorted(files),
            )
        )
    return units


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def extract_changed_symbols(diff_text: str) -> list[str]:
    """
    Extract function/class names from added lines in a unified diff.
    Mirrors claw-code's prompt tokenization: changed symbols become the 'query tokens'
    used to score which documentation sections are most relevant to update.
    """
    symbols: list[str] = []
    for line in diff_text.splitlines():
        if not line.startswith('+') or line.startswith('+++'):
            continue
        m = re.match(r'^\+\s*(def|class)\s+(\w+)', line)
        if m:
            symbols.append(m.group(2))
    return list(dict.fromkeys(symbols))  # dedupe, preserve order


def score_doc_sections(
    existing_doc: str,
    symbols: list[str],
) -> list[tuple[str, str]]:
    """
    Split existing_doc into H2 sections and score each against changed symbols.
    Mirrors claw-code's _score(): count how many symbol tokens appear in each section.
    Returns sections sorted by relevance (desc). Overview is always surfaced first.
    """
    if not existing_doc or not symbols:
        return []

    sections: list[tuple[str, str]] = []
    current_heading = ""
    current_lines: list[str] = []

    for line in existing_doc.splitlines():
        if line.startswith("## "):
            if current_heading:
                sections.append((current_heading, "\n".join(current_lines).strip()))
            current_heading = line.lstrip("# ").strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_heading:
        sections.append((current_heading, "\n".join(current_lines).strip()))

    symbol_tokens = {s.lower() for s in symbols}

    def _section_score(heading: str, body: str) -> int:
        haystack = (heading + " " + body).lower()
        return sum(1 for tok in symbol_tokens if tok in haystack)

    scored = sorted(sections, key=lambda s: _section_score(s[0], s[1]), reverse=True)
    overview = [(h, b) for h, b in scored if h.lower() == "overview"]
    rest = [(h, b) for h, b in scored if h.lower() != "overview"]
    return overview + rest


def _keyword_density_score(content: str, kind: str) -> int:
    """Score file content by keyword frequency relative to unit kind (claw-code routing pattern)."""
    patterns = KIND_PRIMARY_PATTERNS.get(kind, set())
    if not patterns:
        return 0
    tokens = re.findall(r'\w+', content.lower())
    matches = sum(1 for t in tokens if t in patterns)
    return min(matches * 10, 300)


def score_file_importance(
    path: str,
    content: str,
    changed_files: set[str],
    unit_kind: str,
) -> int:
    score = 0
    name = Path(path).stem.lower()
    line_count = len(content.splitlines())

    if path in changed_files:
        score += 1000

    # Primary file for unit kind
    primary_patterns = KIND_PRIMARY_PATTERNS.get(unit_kind, set())
    if any(pattern in name for pattern in primary_patterns):
        score += 500

    # Model/schema file
    if any(keyword in name for keyword in ("model", "schema", "entity")):
        score += 400

    # Not a helper
    if not any(hint in name for hint in HELPER_NAME_HINTS):
        score += 200

    if line_count > 50:
        score += 100

    score += _keyword_density_score(content, unit_kind)

    # Test file penalty
    if "test" in name or "spec" in name:
        score -= 300

    if any(hint in name for hint in HELPER_NAME_HINTS):
        score -= 200

    if line_count < 20:
        score -= 100

    return score


def select_files_within_budget(
    ranked_files: list[tuple[str, str]],
    token_budget: int,
    max_files_fulltext: int,
    max_file_chars: int,
) -> list[tuple[str, str]]:
    """Select files within token budget, with possible partial truncation of last."""
    selected: list[tuple[str, str]] = []
    used_tokens = 0

    for path, content in ranked_files:
        if len(selected) >= max_files_fulltext:
            break

        content_tokens = estimate_tokens(content)

        if used_tokens + content_tokens <= token_budget:
            # Truncate content if too long in chars
            if len(content) > max_file_chars:
                content = content[:max_file_chars] + "\n\n...[truncated]...\n"
            selected.append((path, content))
            used_tokens += content_tokens
        elif not selected:
            # Always include at least one file, possibly truncated
            budget_chars = token_budget * 4
            content = content[:budget_chars] + "\n\n...[truncated]...\n"
            selected.append((path, content))
            break
        else:
            # Partial include of remaining budget
            remaining_chars = (token_budget - used_tokens) * 4
            if remaining_chars > 200:
                content = content[:remaining_chars] + "\n\n...[truncated]...\n"
                selected.append((path, content))
            break

    return selected


def gather_neighbour_summaries(
    repo: Path,
    unit: DocumentationUnit,
    all_units: list[DocumentationUnit],
    deps: dict[str, set[str]],
    max_neighbours: int = 3,
) -> list[tuple[str, str]]:
    """Find units sharing imports with this unit and return their doc snippets."""
    # Find which other units share imports
    neighbours: list[tuple[int, DocumentationUnit]] = []

    for other in all_units:
        if other.slug == unit.slug:
            continue
        other_file_set = set(other.files)

        # Count cross-unit imports
        cross_imports = sum(
            1 for f in unit.files
            for dep in deps.get(f, set())
            if dep in other_file_set
        )
        if cross_imports > 0:
            neighbours.append((cross_imports, other))

    neighbours.sort(key=lambda x: x[0], reverse=True)
    top_neighbours = [u for _, u in neighbours[:max_neighbours]]

    summaries: list[tuple[str, str]] = []
    for neighbour in top_neighbours:
        doc_path = repo / AUTODOC_DIR / "units" / f"{neighbour.slug}.md"
        if doc_path.exists():
            try:
                snippet = doc_path.read_text(encoding="utf-8")[:500]
                summaries.append((neighbour.name, snippet))
            except Exception:
                pass

    return summaries


def build_unit_context_bundle(
    repo: Path,
    base: str,
    head: str,
    unit: DocumentationUnit,
    *,
    include_diff: bool,
    changed_files: set[str],
    max_file_chars: int = 6000,
    max_files_fulltext: int = 8,
    token_budget: int = 12000,
    all_units: list[DocumentationUnit] | None = None,
    deps: dict[str, set[str]] | None = None,
    repo_manifest: str = "",
) -> UnitContextBundle:
    readme_content = _read_readme_if_present(repo)
    existing_doc = _read_existing_unit_doc(repo, unit.slug)

    raw_contents: list[tuple[str, str]] = []
    diffs: list[tuple[str, str]] = []

    for file_path in unit.files:
        full_path = repo / file_path

        if full_path.exists():
            content = _read_text_file(full_path)
        else:
            content = read_file_at_head(repo, head, file_path)

        raw_contents.append((file_path, content))

        if include_diff and file_path in changed_files:
            diff_text = get_file_diff(repo, base, head, file_path)
            if diff_text.strip():
                diffs.append((file_path, diff_text))

    # Score and rank files
    scored = sorted(
        raw_contents,
        key=lambda item: score_file_importance(item[0], item[1], changed_files, unit.kind),
        reverse=True,
    )

    selected = select_files_within_budget(scored, token_budget, max_files_fulltext, max_file_chars)

    # Gather neighbour summaries if deps available
    neighbour_summaries: list[tuple[str, str]] = []
    if deps is not None and all_units is not None:
        neighbour_summaries = gather_neighbour_summaries(repo, unit, all_units, deps)

    # Extract changed symbols from diffs (claw-code tokenization pattern)
    all_symbols: list[str] = []
    for _, diff_text in diffs:
        all_symbols.extend(extract_changed_symbols(diff_text))

    # Score existing doc sections against changed symbols (claw-code _score() pattern)
    scored_doc_sections = score_doc_sections(existing_doc, all_symbols) if all_symbols else []

    return UnitContextBundle(
        unit_name=unit.name,
        unit_slug=unit.slug,
        unit_kind=unit.kind,
        unit_root=unit.root,
        readme_content=readme_content,
        existing_unit_doc=existing_doc,
        files=unit.files,
        file_contents=selected,
        diffs=diffs,
        neighbour_summaries=neighbour_summaries,
        repo_manifest=repo_manifest,
        changed_symbols=all_symbols,
        scored_doc_sections=scored_doc_sections,
    )
