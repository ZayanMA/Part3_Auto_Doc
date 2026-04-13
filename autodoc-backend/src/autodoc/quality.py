from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


REQUIRED_SECTIONS = [
    "Overview",
    "Responsibilities",
    "Key APIs & Interfaces",
    "Configuration & Data",
    "Dependencies",
    "Usage Notes",
]


@dataclass
class UnitQualityReport:
    slug: str
    name: str
    kind: str
    section_completeness: float       # 0.0–1.0 (required H2s present)
    missing_sections: list[str]       # which required sections are absent
    content_density: dict             # {word_count, code_block_count, link_count}
    technical_coverage: float         # 0.0–1.0 (public symbols mentioned in doc)
    uncovered_symbols: list[str]      # source symbols absent from doc
    readability_grade: float          # Flesch-Kincaid grade level
    readability_ease: float           # Flesch reading ease (0–100)
    hallucination_risk: float         # 0.0–1.0 (backtick tokens not found in source)
    unverified_tokens: list[str]      # specific unverified code references
    overall_score: float              # weighted average


@dataclass
class RepoQualityReport:
    units: list[UnitQualityReport]
    avg_section_completeness: float
    avg_technical_coverage: float
    avg_overall_score: float
    avg_readability_grade: float


def score_section_completeness(markdown: str) -> tuple[float, list[str]]:
    """Check which required H2 sections are present."""
    found: set[str] = set()
    for line in markdown.splitlines():
        m = re.match(r'^##\s+(.+)', line)
        if m:
            found.add(m.group(1).strip())

    missing = [s for s in REQUIRED_SECTIONS if s not in found]
    score = 1.0 - len(missing) / len(REQUIRED_SECTIONS)
    return score, missing


def score_content_density(markdown: str) -> dict:
    """Count words (stripped), fenced code blocks, and links."""
    # Strip fenced code blocks for word count
    no_code = re.sub(r'```[\s\S]*?```', '', markdown)
    # Strip markdown syntax
    no_markup = re.sub(r'[#*_`>\[\]()!]', ' ', no_code)
    words = [w for w in no_markup.split() if w.strip()]
    word_count = len(words)

    code_block_count = len(re.findall(r'```', markdown)) // 2
    link_count = len(re.findall(r'\[([^\]]+)\]\(([^)]+)\)', markdown))

    return {
        "word_count": word_count,
        "code_block_count": code_block_count,
        "link_count": link_count,
    }


def _extract_source_symbols(source_files: list[str], repo_path: Optional[Path] = None) -> list[str]:
    """Extract public symbol names from source files (Python + JS/TS)."""
    symbols: list[str] = []

    for file_path in source_files:
        if repo_path:
            full_path = repo_path / file_path
        else:
            full_path = Path(file_path)

        if not full_path.exists():
            continue

        try:
            content = full_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        suffix = Path(file_path).suffix.lower()
        if suffix == ".py":
            for m in re.finditer(r'^(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)', content, re.MULTILINE):
                name = m.group(1)
                if not name.startswith("_"):
                    symbols.append(name)
        elif suffix in (".js", ".ts", ".jsx", ".tsx"):
            for pattern in [
                r'\bfunction\s+([A-Za-z_$][A-Za-z0-9_$]*)',
                r'\bclass\s+([A-Za-z_$][A-Za-z0-9_$]*)',
                r'\bconst\s+([A-Za-z_$][A-Za-z0-9_$]*)\s*=',
                r'\bexport\s+(?:default\s+)?(?:function|class)\s+([A-Za-z_$][A-Za-z0-9_$]*)',
            ]:
                for m in re.finditer(pattern, content):
                    name = m.group(1)
                    if not name.startswith("_"):
                        symbols.append(name)

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for s in symbols:
        if s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def score_technical_coverage(markdown: str, source_files: list[str], repo_path: Optional[Path] = None) -> tuple[float, list[str]]:
    """Check what fraction of public symbols appear in the documentation."""
    symbols = _extract_source_symbols(source_files, repo_path)
    if not symbols:
        return 1.0, []

    uncovered = [s for s in symbols if s not in markdown]
    score = 1.0 - len(uncovered) / len(symbols)
    return score, uncovered


def score_readability(markdown: str) -> tuple[float, float]:
    """Return (flesch_kincaid_grade, flesch_reading_ease) for the doc's prose."""
    try:
        import textstat
    except ImportError:
        return 0.0, 0.0

    # Strip code blocks
    no_code = re.sub(r'```[\s\S]*?```', '', markdown)
    # Strip markdown syntax characters
    plain = re.sub(r'[#*_`>\[\]()!]', ' ', no_code)
    plain = re.sub(r'\s+', ' ', plain).strip()

    if len(plain.split()) < 20:
        return 0.0, 100.0

    grade = textstat.flesch_kincaid_grade(plain)
    ease = textstat.flesch_reading_ease(plain)
    return grade, ease


def score_hallucination_risk(markdown: str, source_files: list[str], repo_path: Optional[Path] = None) -> tuple[float, list[str]]:
    """Check inline `code` references in doc against source corpus."""
    # Extract all backtick-enclosed tokens from doc
    doc_tokens = re.findall(r'`([^`\n]+)`', markdown)
    if not doc_tokens:
        return 0.0, []

    # Build source corpus
    corpus_parts: list[str] = []
    for file_path in source_files:
        if repo_path:
            full_path = repo_path / file_path
        else:
            full_path = Path(file_path)
        if full_path.exists():
            try:
                corpus_parts.append(full_path.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                pass
    corpus = "\n".join(corpus_parts)

    unverified = [t for t in doc_tokens if t not in corpus]
    risk = len(unverified) / len(doc_tokens)
    return risk, unverified


def _density_score(density: dict) -> float:
    """Convert content density dict to 0–1 score."""
    word_count = density.get("word_count", 0)
    code_blocks = density.get("code_block_count", 0)
    # Reasonable doc: 100–600 words, at least 1 code block
    word_score = min(word_count / 300, 1.0)
    code_score = min(code_blocks / 2, 1.0)
    return (word_score * 0.7 + code_score * 0.3)


def _readability_score(grade: float, ease: float) -> float:
    """Convert grade/ease to 0–1 score. Prefer grade 8–12, ease 30–70."""
    if grade == 0 and ease == 100.0:
        return 0.5  # not enough text to score
    # Grade: lower is easier (score lower grade as better, up to 12)
    grade_score = max(0.0, 1.0 - max(0.0, grade - 12) / 10)
    # Ease: higher is easier (score 50–100 as good)
    ease_score = min(ease / 70, 1.0) if ease > 0 else 0.0
    return (grade_score + ease_score) / 2


def compute_overall_score(
    section_completeness: float,
    technical_coverage: float,
    hallucination_risk: float,
    content_density: dict,
    readability_grade: float,
    readability_ease: float,
) -> float:
    """Weighted overall quality score."""
    h_safety = 1.0 - hallucination_risk
    density = _density_score(content_density)
    readability = _readability_score(readability_grade, readability_ease)

    return (
        section_completeness * 0.30
        + technical_coverage * 0.25
        + h_safety * 0.25
        + density * 0.10
        + readability * 0.10
    )


def evaluate_unit(
    slug: str,
    name: str,
    kind: str,
    markdown: str,
    source_files: list[str],
    repo_path: Optional[Path] = None,
) -> UnitQualityReport:
    """Compute full quality report for a single documentation unit."""
    section_completeness, missing_sections = score_section_completeness(markdown)
    content_density = score_content_density(markdown)
    technical_coverage, uncovered_symbols = score_technical_coverage(markdown, source_files, repo_path)
    readability_grade, readability_ease = score_readability(markdown)
    hallucination_risk, unverified_tokens = score_hallucination_risk(markdown, source_files, repo_path)

    overall_score = compute_overall_score(
        section_completeness, technical_coverage, hallucination_risk,
        content_density, readability_grade, readability_ease,
    )

    return UnitQualityReport(
        slug=slug,
        name=name,
        kind=kind,
        section_completeness=round(section_completeness, 3),
        missing_sections=missing_sections,
        content_density=content_density,
        technical_coverage=round(technical_coverage, 3),
        uncovered_symbols=uncovered_symbols[:20],  # cap for response size
        readability_grade=round(readability_grade, 2),
        readability_ease=round(readability_ease, 2),
        hallucination_risk=round(hallucination_risk, 3),
        unverified_tokens=unverified_tokens[:20],
        overall_score=round(overall_score, 3),
    )


def evaluate_repo(
    units_dir: Path,
    source_files_by_slug: dict[str, list[str]],
    repo_path: Optional[Path] = None,
) -> RepoQualityReport:
    """Compute quality reports for all units in the .autodoc/units/ directory."""
    reports: list[UnitQualityReport] = []

    for md_path in sorted(units_dir.glob("*.md")):
        slug = md_path.stem
        try:
            markdown = md_path.read_text(encoding="utf-8")
        except Exception:
            continue

        source_files = source_files_by_slug.get(slug, [])
        report = evaluate_unit(slug, slug, "module", markdown, source_files, repo_path)
        reports.append(report)

    if not reports:
        return RepoQualityReport(
            units=[], avg_section_completeness=0.0,
            avg_technical_coverage=0.0, avg_overall_score=0.0,
            avg_readability_grade=0.0,
        )

    n = len(reports)
    return RepoQualityReport(
        units=reports,
        avg_section_completeness=round(sum(r.section_completeness for r in reports) / n, 3),
        avg_technical_coverage=round(sum(r.technical_coverage for r in reports) / n, 3),
        avg_overall_score=round(sum(r.overall_score for r in reports) / n, 3),
        avg_readability_grade=round(sum(r.readability_grade for r in reports) / n, 2),
    )
