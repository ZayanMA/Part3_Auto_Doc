from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple
import hashlib
from dataclasses import dataclass, field

import typer
from rich.console import Console
from rich.table import Table

from autodoc.cache import (
    AUTODOC_DIR,
    cache_exists,
    compute_cache_key,
    compute_incremental_cache_key,
    get_cache_paths,
    save_cache_entry,
    prune_cache,
    append_changelog_entry,
)
from autodoc.config import AutodocConfig, load_config
from autodoc.context import (
    read_repo_readme,
    group_files_into_units,
    merge_small_groups,
    merge_by_import_coupling,
    make_units_from_groups,
    build_unit_context_bundle,
    apply_unit_overrides,
    estimate_tokens,
    enrich_unit_names,
    verify_units_relevance,
    collapse_homogeneous_siblings,
)
from autodoc.repo_index import (
    load_index,
    save_index,
    build_repo_index,
    diff_indices,
    impacted_units,
    utc_now_iso,
)
from autodoc.filters import get_all_relevant_files_git, get_all_relevant_files, is_probably_text_file
from autodoc.git_utils import GitCommandError, ensure_git_repo, get_changed_files
from autodoc.llm import generate_documentation, generate_repo_documentation
from autodoc.manifest import build_repo_manifest, render_manifest
from autodoc.models import DocumentationUnit, JobUsageSummary
from autodoc.prompts import PROMPT_VERSION, build_repo_prompt, build_unit_prompt, build_unit_patch_prompt
from autodoc.router import RoutingDecision, route_model

app = typer.Typer(help="Automatic documentation generator")
console = Console()


@dataclass
class SessionStats:
    generated: int = 0
    cached: int = 0
    patched: int = 0
    failed: int = 0
    total_cost_usd: float = 0.0
    total_tokens: int = 0


@app.command()
def generate(
    repo: str = typer.Option(".", help="Path to the target repository"),
    base: str = typer.Option("HEAD~1", help="Base git ref"),
    head: str = typer.Option("HEAD", help="Head git ref"),
    model: Optional[str] = typer.Option(None, help="Override model for all units"),
    limit: Optional[int] = typer.Option(None, help="Optional max number of units to process"),
    all_files: bool = typer.Option(False, "--all", help="Generate documentation for all relevant files"),
    debug: bool = typer.Option(False, "--debug", help="Print prompt diagnostics"),
    dump_prompts: bool = typer.Option(False, "--dump-prompts", help="Write full prompts to .autodoc/prompts/"),
    config_path: Optional[str] = typer.Option(None, "--config", help="Path to config TOML"),
    patch: bool = typer.Option(True, "--patch/--no-patch", help="Enable patch mode"),
    prune: bool = typer.Option(True, "--prune-cache/--no-prune-cache", help="Prune old cache entries"),
    costs: bool = typer.Option(True, "--costs/--no-costs", help="Show token/cost column"),
    fast_model: Optional[str] = typer.Option(None, "--fast-model", help="Override fast model"),
    smart_model: Optional[str] = typer.Option(None, "--smart-model", help="Override smart model"),
) -> None:
    repo_path = Path(repo).resolve()

    # 1. Load config, apply CLI overrides
    cfg_file = Path(config_path) if config_path else None
    cfg = load_config(repo_path, cfg_file)
    if fast_model:
        cfg.fast_model = fast_model
    if smart_model:
        cfg.smart_model = smart_model
    if not patch:
        cfg.patch_mode_enabled = False
    # If explicit model override, treat as smart model for all
    if model:
        cfg.fast_model = model
        cfg.smart_model = model

    # 2. Ensure git repo
    try:
        ensure_git_repo(repo_path)
    except GitCommandError as e:
        console.print(f"[red]Git error:[/red] {e}")
        raise typer.Exit(code=1)

    # 3. Get all relevant files (git-aware fallback)
    all_candidates = get_all_relevant_files_git(repo_path)
    all_paths = [c.path for c in all_candidates]

    # 4. Apply unit overrides first
    raw_groups = group_files_into_units(all_paths)
    raw_groups = apply_unit_overrides(raw_groups, cfg.unit_overrides, all_paths)

    # 5. Build import graph
    try:
        from autodoc.repo_index import build_import_graph
        _raw_imports, _resolved = build_import_graph(repo_path, all_paths)
        # Convert list values to sets for O(1) membership checks
        deps: dict[str, set[str]] = {k: set(v) for k, v in _resolved.items()}
    except Exception:
        deps = {}

    # 6-8. Group, couple-merge, size-merge
    groups = merge_by_import_coupling(raw_groups, deps)
    groups = merge_small_groups(groups, min_files=cfg.min_files_per_unit)

    # 9. Make units with kind detection, then enrich names + filter relevance
    all_units = make_units_from_groups(groups)
    all_units = enrich_unit_names(all_units, repo_path, cfg.fast_model)
    all_units = verify_units_relevance(all_units, repo_path, cfg.fast_model)

    if not all_units:
        console.print("[yellow]No relevant units found.[/yellow]")
        raise typer.Exit(code=0)

    # Build repo manifest once — injected into every unit prompt (claw-code PortManifest pattern)
    repo_manifest_obj = build_repo_manifest(repo_path, all_units, all_paths)
    repo_manifest_text = render_manifest(repo_manifest_obj)

    # 10. Determine changed files
    changed_files_set: set[str] = set()
    if all_files:
        changed_files_set = set(all_paths)
    else:
        try:
            changed = get_changed_files(repo_path, base, head)
            changed_files_set = {
                c.path for c in changed
                if c.status != "D" and is_probably_text_file(c.path)
            }
        except Exception as e:
            console.print(f"[red]Failed to gather changed files:[/red] {e}")
            raise typer.Exit(code=1)

    # 11. Build repo index + determine impacted units
    old_idx = load_index(repo_path)
    new_idx = build_repo_index(repo_path, all_units, all_paths)
    struct = diff_indices(old_idx, new_idx)

    if all_files:
        units_to_run = all_units
    else:
        impacted_roots = set()
        impacted_roots.update(struct.get("added_units", []))
        impacted_roots.update(struct.get("changed_units", []))
        impacted_roots.update(impacted_units(new_idx, changed_files_set, depth=2))
        units_to_run = [u for u in all_units if u.root in impacted_roots]

    if limit is not None:
        units_to_run = units_to_run[:limit]

    if not units_to_run:
        console.print("[yellow]No impacted units to regenerate.[/yellow]")
        new_idx.updated_at_utc = utc_now_iso()
        save_index(repo_path, new_idx)
        raise typer.Exit(code=0)

    # 12. Prune cache if enabled
    if prune:
        pruned = prune_cache(repo_path, cfg.cache_max_age_days)
        if pruned > 0:
            console.print(f"[dim]Pruned {pruned} stale cache entries.[/dim]")

    # Summary table
    summary = Table(title="Autodoc Generation Summary (Units)")
    summary.add_column("Unit", style="bold")
    summary.add_column("Root")
    summary.add_column("Files", justify="right")
    summary.add_column("Changed", justify="right")
    summary.add_column("Model")
    summary.add_column("Mode")
    summary.add_column("Result")
    if costs:
        summary.add_column("Tokens", justify="right")
        summary.add_column("Cost $", justify="right")
    summary.add_column("Doc")

    stats = SessionStats()
    job_usage = JobUsageSummary()
    per_unit_markdown_paths: List[Tuple[str, Path]] = []

    units_dir = repo_path / AUTODOC_DIR / "units"
    units_dir.mkdir(parents=True, exist_ok=True)

    if dump_prompts:
        prompts_dir = repo_path / AUTODOC_DIR / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
    else:
        prompts_dir = None

    # 13. Process each unit
    for unit in units_to_run:
        file_count = str(len(unit.files))
        changed_count = "-" if all_files else str(sum(1 for f in unit.files if f in changed_files_set))

        stable_path = units_dir / f"{unit.slug}.md"
        stable_rel = str(stable_path.relative_to(repo_path))

        try:
            bundle = build_unit_context_bundle(
                repo_path,
                base,
                head,
                unit,
                include_diff=not all_files,
                changed_files=changed_files_set,
                max_file_chars=cfg.max_file_chars,
                max_files_fulltext=cfg.max_files_fulltext,
                token_budget=cfg.token_budget,
                all_units=all_units,
                deps=deps,
                repo_manifest=repo_manifest_text,
            )

            # Route model + mode
            decision = route_model(unit, changed_files_set, bundle.diffs, bundle.existing_unit_doc, cfg)

            # Select prompt
            if decision.mode == "patch" and bundle.diffs:
                prompt_text = build_unit_patch_prompt(bundle)
            else:
                prompt_text = build_unit_prompt(bundle)

            if prompts_dir is not None:
                (prompts_dir / f"{unit.slug}.prompt.txt").write_text(prompt_text, encoding="utf-8")

            if debug:
                h = hashlib.sha256(prompt_text.encode()).hexdigest()[:12]
                console.print(f"[dim]Prompt SHA={h} chars={len(prompt_text)} unit={unit.slug} model={decision.model} mode={decision.mode}[/dim]")

            # Compute cache key
            if decision.mode == "patch" and bundle.diffs:
                changed_files_content = {
                    p: c for p, c in bundle.file_contents if p in changed_files_set
                }
                cache_key = compute_incremental_cache_key(
                    unit.slug, changed_files_content, bundle.existing_unit_doc,
                    decision.model, PROMPT_VERSION,
                )
            else:
                cache_key = compute_cache_key(
                    target_file=unit.slug,
                    prompt_text=prompt_text,
                    model_name=decision.model,
                    prompt_version=PROMPT_VERSION,
                )

            if cache_exists(repo_path, cache_key):
                md_path, _ = get_cache_paths(repo_path, cache_key)
                stats.cached += 1
                job_usage = job_usage.add_cached()
                per_unit_markdown_paths.append((unit.name, md_path))

                try:
                    stable_path.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
                except Exception:
                    pass

                row = [unit.name, unit.root, file_count, changed_count,
                       decision.model.split("/")[-1], decision.mode, "cached"]
                if costs:
                    row += ["-", "-"]
                row.append(stable_rel)
                summary.add_row(*row)
                continue

            markdown, usage = generate_documentation(prompt_text, unit.slug, model=decision.model)
            md_path, _ = save_cache_entry(
                repo=repo_path,
                cache_key=cache_key,
                markdown=markdown,
                source_file=unit.root,
                model_name=decision.model,
                prompt_version=PROMPT_VERSION,
                base_ref=base,
                head_ref=head,
                mode=decision.mode,
                routing_reason=decision.reason,
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                estimated_cost_usd=usage.estimated_cost_usd,
            )

            append_changelog_entry(stable_path, decision.mode, decision.model, base, head)

            if decision.mode == "patch":
                stats.patched += 1
            else:
                stats.generated += 1

            stats.total_cost_usd += usage.estimated_cost_usd
            stats.total_tokens += usage.prompt_tokens + usage.completion_tokens
            job_usage = job_usage.add(usage.prompt_tokens, usage.completion_tokens)

            per_unit_markdown_paths.append((unit.name, md_path))

            try:
                stable_path.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
            except Exception:
                pass

            result_label = "patched" if decision.mode == "patch" else "generated"
            row = [unit.name, unit.root, file_count, changed_count,
                   decision.model.split("/")[-1], decision.mode, result_label]
            if costs:
                total_tok = usage.prompt_tokens + usage.completion_tokens
                row += [str(total_tok), f"{usage.estimated_cost_usd:.4f}"]
            row.append(stable_rel)
            summary.add_row(*row)

        except Exception as e:
            stats.failed += 1
            row = [unit.name, unit.root, file_count, changed_count, "-", "-", "failed"]
            if costs:
                row += ["-", "-"]
            row.append(str(e)[:60])
            summary.add_row(*row)

    console.print(summary)

    # 15. Repo overview with smart model
    repo_readme = read_repo_readme(repo_path)
    unit_docs: List[Tuple[str, str]] = []

    for p in sorted(units_dir.glob("*.md")):
        try:
            content = p.read_text(encoding="utf-8")
        except Exception:
            continue

        # Use token-budget-based truncation instead of hardcoded 4000
        max_chars = cfg.token_budget * 4
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n...[truncated]...\n"
        unit_docs.append((p.stem, content))

    if unit_docs:
        repo_prompt = build_repo_prompt(
            repo_name=repo_path.name,
            readme_content=repo_readme,
            file_docs=unit_docs,
        )

        if debug:
            h = hashlib.sha256(repo_prompt.encode()).hexdigest()[:12]
            console.print(f"[dim]Repo prompt SHA={h} chars={len(repo_prompt)}[/dim]")

        repo_markdown = generate_repo_documentation(repo_prompt, model=cfg.smart_model)

        repo_doc_path = repo_path / AUTODOC_DIR / "REPOSITORY.md"
        repo_doc_path.write_text(repo_markdown, encoding="utf-8")
        console.print(f"\n[bold]Repository documentation written to:[/bold] {repo_doc_path}")

    # 16. Save updated repo index
    new_idx.updated_at_utc = utc_now_iso()
    save_index(repo_path, new_idx)

    # 17. Print session totals
    console.print(
        f"\n[bold]Done.[/bold] "
        f"generated={stats.generated}, "
        f"patched={stats.patched}, "
        f"cached={stats.cached}, "
        f"failed={stats.failed}"
        + (f", total_tokens={stats.total_tokens}, est_cost=${stats.total_cost_usd:.4f}" if costs else "")
    )
    console.print(
        f"[dim]Job usage: in={job_usage.input_tokens} out={job_usage.output_tokens} "
        f"units_processed={job_usage.units_processed} units_cached={job_usage.units_cached}[/dim]"
    )


@app.command()
def evaluate(
    repo: str = typer.Option(".", help="Path to the target repository"),
    output: str = typer.Option("table", help="Output format: table or json"),
    out: Optional[str] = typer.Option(None, "--out", help="Write JSON output to this file"),
) -> None:
    """Evaluate documentation quality for all generated units."""
    import json as _json
    from autodoc.quality import evaluate_unit, RepoQualityReport

    repo_path = Path(repo).resolve()
    units_dir = repo_path / AUTODOC_DIR / "units"

    if not units_dir.exists():
        console.print(f"[red]No units directory found at:[/red] {units_dir}")
        raise typer.Exit(code=1)

    # Load index.json for file lists
    index_path = repo_path / AUTODOC_DIR / "index.json"
    files_by_slug: dict[str, list[str]] = {}
    if index_path.exists():
        try:
            idx = _json.loads(index_path.read_text(encoding="utf-8"))
            for unit in idx.get("units", []):
                files_by_slug[unit["slug"]] = unit.get("files", [])
        except Exception:
            pass

    reports = []
    for md_path in sorted(units_dir.glob("*.md")):
        slug = md_path.stem
        try:
            markdown = md_path.read_text(encoding="utf-8")
        except Exception:
            continue
        source_files = files_by_slug.get(slug, [])
        report = evaluate_unit(slug, slug, "module", markdown, source_files, repo_path)
        reports.append(report)

    if not reports:
        console.print("[yellow]No unit documentation found to evaluate.[/yellow]")
        raise typer.Exit(code=0)

    if output == "json" or out:
        data = [r.__dict__ for r in reports]
        json_str = _json.dumps(data, indent=2)
        if out:
            Path(out).write_text(json_str, encoding="utf-8")
            console.print(f"[green]Quality scores written to:[/green] {out}")
        else:
            console.print(json_str)
        return

    # Rich table output
    table = Table(title="Documentation Quality Scores")
    table.add_column("Unit", style="bold")
    table.add_column("Sections", justify="right")
    table.add_column("Coverage", justify="right")
    table.add_column("Hallucination", justify="right")
    table.add_column("Words", justify="right")
    table.add_column("Grade", justify="right")
    table.add_column("Overall", justify="right")

    for r in reports:
        sections_str = f"{int(r.section_completeness * 6)}/6"
        coverage_str = f"{r.technical_coverage:.0%}"
        halluc_str = f"{r.hallucination_risk:.0%}"
        words_str = str(r.content_density.get("word_count", 0))
        grade_str = f"{r.readability_grade:.1f}"

        score = r.overall_score
        if score >= 0.75:
            overall_str = f"[green]{score:.2f}[/green]"
        elif score >= 0.5:
            overall_str = f"[yellow]{score:.2f}[/yellow]"
        else:
            overall_str = f"[red]{score:.2f}[/red]"

        table.add_row(r.slug, sections_str, coverage_str, halluc_str, words_str, grade_str, overall_str)

    console.print(table)

    n = len(reports)
    avg_score = sum(r.overall_score for r in reports) / n
    avg_coverage = sum(r.technical_coverage for r in reports) / n
    avg_sections = sum(r.section_completeness for r in reports) / n
    console.print(
        f"\n[bold]Averages:[/bold] "
        f"overall={avg_score:.2f}, "
        f"sections={avg_sections:.0%}, "
        f"coverage={avg_coverage:.0%}"
    )


if __name__ == "__main__":
    app()
