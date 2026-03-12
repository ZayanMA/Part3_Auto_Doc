from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import typer
from rich.console import Console
from rich.table import Table
import hashlib

from autodoc.cache import (
    AUTODOC_DIR,
    cache_exists,
    compute_cache_key,
    get_cache_paths,
    save_cache_entry,
)
from autodoc.context import (
    read_repo_readme,
    group_files_into_units,
    merge_small_groups,
    make_units_from_groups,
    build_unit_context_bundle,
)
from autodoc.filters import get_all_relevant_files, is_probably_text_file
from autodoc.git_utils import GitCommandError, ensure_git_repo, get_changed_files
from autodoc.llm import DEFAULT_MODEL_NAME, generate_documentation, generate_repo_documentation
from autodoc.prompts import PROMPT_VERSION, build_repo_prompt, build_unit_prompt

app = typer.Typer(help="Automatic documentation generator")
console = Console()


@app.command()
def generate(
    repo: str = typer.Option(".", help="Path to the target repository"),
    base: str = typer.Option("HEAD~1", help="Base git ref"),
    head: str = typer.Option("HEAD", help="Head git ref"),
    model: str = typer.Option(DEFAULT_MODEL_NAME, help="Model name used for generation"),
    limit: Optional[int] = typer.Option(None, help="Optional max number of units to process"),
    all_files: bool = typer.Option(False, "--all", help="Generate documentation for all relevant files"),
    debug: bool = typer.Option(False, "--debug", help="Print prompt diagnostics"),
    dump_prompts: bool = typer.Option(False, "--dump-prompts", help="Write full prompts to .autodoc/prompts/"),
) -> None:
    repo_path = Path(repo).resolve()

    try:
        ensure_git_repo(repo_path)
    except GitCommandError as e:
        console.print(f"[red]Git error:[/red] {e}")
        raise typer.Exit(code=1)

    # Gather either all relevant files or only changed relevant files.
    try:
        if all_files:
            candidates = get_all_relevant_files(repo_path)
        else:
            changed = get_changed_files(repo_path, base, head)
            candidates = [
                item for item in changed
                if item.status != "D" and is_probably_text_file(item.path)
            ]
    except Exception as e:
        console.print(f"[red]Failed to gather files:[/red] {e}")
        raise typer.Exit(code=1)

    candidate_paths = [c.path for c in candidates]

    groups = group_files_into_units(candidate_paths)
    groups = merge_small_groups(groups, min_files=3)
    units = make_units_from_groups(groups)

    if limit is not None:
        units = units[:limit]

    if not units:
        console.print("[yellow]No relevant units found.[/yellow]")
        raise typer.Exit(code=0)

    # Summary table
    summary = Table(title="Autodoc Generation Summary (Units)")
    summary.add_column("Unit", style="bold")
    summary.add_column("Root")
    summary.add_column("Files", justify="right")
    summary.add_column("Changed", justify="right")
    summary.add_column("Result")
    summary.add_column("Doc")

    generated_count = 0
    cached_count = 0
    failed_count = 0

    # (unit name, generated markdown path)
    per_unit_markdown_paths: List[Tuple[str, Path]] = []

    # Stable output dir (optional but nice)
    units_dir = repo_path / AUTODOC_DIR / "units"
    units_dir.mkdir(parents=True, exist_ok=True)

    changed_set = set()
    if not all_files:
        changed_set = {c.path for c in candidates}

    for unit in units:
        # Compute these up-front so they're always defined
        file_count = str(len(unit.files))
        changed_count = "-" if all_files else str(sum(1 for f in unit.files if f in changed_set))

        stable_path = units_dir / f"{unit.slug}.md"
        stable_rel = str(stable_path.relative_to(repo_path))

        try:
            bundle = build_unit_context_bundle(
                repo_path,
                base,
                head,
                unit,
                include_diff=not all_files,
            )
            prompt_text = build_unit_prompt(bundle)
            if dump_prompts:
                prompts_dir = repo_path / AUTODOC_DIR / "prompts"
                prompts_dir.mkdir(parents=True, exist_ok=True)
                prompt_path = prompts_dir / f"{unit.slug}.prompt.txt"
                prompt_path.write_text(prompt_text, encoding="utf-8")

            cache_key = compute_cache_key(
                target_file=unit.slug,
                prompt_text=prompt_text,
                model_name=model,
                prompt_version=PROMPT_VERSION,
            )

            if cache_exists(repo_path, cache_key):
                md_path, _ = get_cache_paths(repo_path, cache_key)

                summary.add_row(
                    str(unit.name),
                    str(unit.root),
                    file_count,
                    changed_count,
                    "cached",
                    stable_rel,
                )
                cached_count += 1
                per_unit_markdown_paths.append((unit.name, md_path))

                # ensure stable copy exists
                try:
                    stable_path.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
                except Exception:
                    pass

                continue
            if debug:
                h = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:12]
                console.print(f"[dim]Prompt SHA={h} chars={len(prompt_text)} unit={unit.slug}[/dim]")
                console.print(f"[dim]Prompt preview:[/dim]\n{prompt_text[:400]}\n[dim]...[/dim]")
            markdown = generate_documentation(prompt_text, unit.slug, model=model)
            md_path, _ = save_cache_entry(
                repo=repo_path,
                cache_key=cache_key,
                markdown=markdown,
                source_file=unit.root,
                model_name=model,
                prompt_version=PROMPT_VERSION,
                base_ref=base,
                head_ref=head,
            )

            summary.add_row(
                str(unit.name),
                str(unit.root),
                file_count,
                changed_count,
                "generated",
                stable_rel,
            )
            generated_count += 1
            per_unit_markdown_paths.append((unit.name, md_path))

            # write stable copy
            try:
                stable_path.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
            except Exception:
                pass

        except Exception as e:
            summary.add_row(
                str(unit.name),
                str(unit.root),
                file_count,
                changed_count,
                "failed",
                str(e),
            )
            failed_count += 1

    console.print(summary)

    # Repository-level documentation from unit docs
    if per_unit_markdown_paths:
        repo_readme = read_repo_readme(repo_path)

        unit_docs: List[Tuple[str, str]] = []
        for unit_name, md_path in per_unit_markdown_paths:
            try:
                content = md_path.read_text(encoding="utf-8")
            except Exception:
                continue

            max_chars = 4000
            if len(content) > max_chars:
                content = content[:max_chars] + "\n\n...[truncated]...\n"

            unit_docs.append((unit_name, content))

        if unit_docs:
            repo_prompt = build_repo_prompt(
                repo_name=repo_path.name,
                readme_content=repo_readme,
                file_docs=unit_docs,  # you can rename this arg later
            )
            if debug:
                h = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()[:12]
                console.print(f"[dim]Prompt SHA={h} chars={len(prompt_text)} unit={unit.slug}[/dim]")
                console.print(f"[dim]Prompt preview:[/dim]\n{prompt_text[:400]}\n[dim]...[/dim]")
            repo_markdown = generate_repo_documentation(repo_prompt, model=model)

            repo_doc_dir = repo_path / AUTODOC_DIR
            repo_doc_dir.mkdir(parents=True, exist_ok=True)
            repo_doc_path = repo_doc_dir / "REPOSITORY.md"
            repo_doc_path.write_text(repo_markdown, encoding="utf-8")

            console.print(f"\n[bold]Repository documentation written to:[/bold] {repo_doc_path}")

    console.print(f"\n[bold]Done.[/bold] generated={generated_count}, cached={cached_count}, failed={failed_count}")


if __name__ == "__main__":
    app()