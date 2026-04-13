from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from autodoc.config import AutodocConfig
from autodoc.models import DocumentationUnit

# Keywords that indicate high-value units requiring the smart model.
# Mirrors claw-code's token-scoring approach: unit name/path tokens are
# matched against a curated keyword set, and high-scoring units are
# promoted to smart_model regardless of size.
_SMART_MODEL_KEYWORDS = {
    "security", "auth", "authentication", "authorization",
    "payment", "billing", "invoice", "checkout",
    "encrypt", "decrypt", "crypto", "token", "jwt", "oauth", "hmac",
    "permission", "role", "acl", "rbac",
    "database", "migration", "transaction", "schema",
    "webhook", "secret", "credential", "password",
}


@dataclass
class RoutingDecision:
    model: str
    mode: str      # "full" | "patch"
    reason: str


def _unit_content_score(unit: DocumentationUnit) -> int:
    """
    Score a unit by keyword presence in its name and file paths.
    Mirrors claw-code's _score(): count how many keyword tokens appear
    in the unit's name/path 'haystacks'. Score >= 2 → smart model.
    """
    name_tokens = set(
        unit.name.lower().replace("_", " ").replace("-", " ").split()
    )
    path_tokens = {
        part.lower()
        for f in unit.files
        for part in Path(f).parts
    }
    all_tokens = name_tokens | path_tokens
    return sum(1 for kw in _SMART_MODEL_KEYWORDS if kw in all_tokens)


def _diff_complexity(diffs: list[tuple[str, str]]) -> int:
    """
    Score diffs structurally (mirrors claw-code's token scoring applied to code changes).
    Weights: new/changed def/class = 10, import change = 5, generic added line = 1.
    """
    score = 0
    for _, diff_text in diffs:
        for line in diff_text.splitlines():
            if not line.startswith('+') or line.startswith('+++'):
                continue
            if re.match(r'^\+\s*(def|class)\s+', line):
                score += 10
            elif re.match(r'^\+\s*(import|from)\s+', line):
                score += 5
            else:
                score += 1
    return score


def route_model(
    unit: DocumentationUnit,
    changed_files: set[str],
    diffs: list[tuple[str, str]],
    existing_doc: str,
    cfg: AutodocConfig,
) -> RoutingDecision:
    # 1. Repo-level overview
    if unit.kind == "overview":
        return RoutingDecision(model=cfg.smart_model, mode="full", reason="repo overview")

    # 2. No existing doc (new unit)
    if not existing_doc.strip():
        return RoutingDecision(model=cfg.smart_model, mode="full", reason="new unit")

    # 3. High-value content (security, auth, payment…) → smart model always
    content_score = _unit_content_score(unit)
    if content_score >= 2:
        return RoutingDecision(
            model=cfg.smart_model, mode="full",
            reason=f"high-value content (score={content_score})",
        )

    # 3. Large unit
    if len(unit.files) > 5:
        return RoutingDecision(model=cfg.smart_model, mode="full", reason="large unit (>5 files)")

    # 4. Small complexity diff → patch mode (structural score, not raw line count)
    complexity = _diff_complexity(diffs)
    if complexity < cfg.patch_diff_threshold and cfg.patch_mode_enabled and diffs:
        return RoutingDecision(model=cfg.fast_model, mode="patch", reason=f"low complexity ({complexity})")

    # 5. >50% of unit files changed
    changed_in_unit = sum(1 for f in unit.files if f in changed_files)
    if unit.files and changed_in_unit / len(unit.files) > 0.5:
        return RoutingDecision(model=cfg.smart_model, mode="full", reason=">50% files changed")

    # 6. Default
    return RoutingDecision(model=cfg.fast_model, mode="full", reason="default")
