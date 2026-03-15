from __future__ import annotations

from dataclasses import dataclass
from autodoc.config import AutodocConfig
from autodoc.models import DocumentationUnit


@dataclass
class RoutingDecision:
    model: str
    mode: str      # "full" | "patch"
    reason: str


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

    # 3. Large unit
    total_lines = sum(len(d.splitlines()) for _, d in diffs)
    if len(unit.files) > 5:
        return RoutingDecision(model=cfg.smart_model, mode="full", reason="large unit (>5 files)")

    # 4. Small diff → patch mode
    if total_lines < cfg.patch_diff_threshold and cfg.patch_mode_enabled and diffs:
        return RoutingDecision(model=cfg.fast_model, mode="patch", reason=f"small diff ({total_lines} lines)")

    # 5. >50% of unit files changed
    changed_in_unit = sum(1 for f in unit.files if f in changed_files)
    if unit.files and changed_in_unit / len(unit.files) > 0.5:
        return RoutingDecision(model=cfg.smart_model, mode="full", reason=">50% files changed")

    # 6. Default
    return RoutingDecision(model=cfg.fast_model, mode="full", reason="default")
