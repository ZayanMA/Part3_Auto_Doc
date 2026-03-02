from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import typer
from rich.console import Console
from rich.table import Table

from autodoc.cache import AUTODOC_DIR, cache_exists, compute_cache_key, get_cache_paths, save_cache_entry
from autodoc.context import build_context_bundle, read_repo_readme
from autodoc.filters import get_all_relevant_files, is_probably_text_file
from autodoc.git_utils import GitCommandError, ensure_git_repo, get_changed_files
from autodoc.llm import DEFAULT_MODEL_NAME, generate_documentation, generate_repo_documentation
from autodoc.prompts import PROMPT_VERSION, build_prompt, build_repo_prompt

app = typer.Typer(help="Automatic documentation generator")
console = Console()


@app.command()
def generate(
    repo: str = typer.Option(".", help="Path to the target repository"),
    base: str = typer.Option("HEAD~1", help="Base git ref"),
    head: str = typer.Option("HEAD", help="Head git ref"),
    model: str = typer.Option(DEFAULT_MODEL_NAME, help="Model name used for generation"),
    limit: Optional[int] = typer.Option(None, help="Optional max number of files to process"),
    all_files: bool = typer.Option(False, "--all", help="Generate documentation for all relevant files"),
) -> None:
    """
    Generate documentation for repository files and produce a repository-level summary.

    This command can operate in two modes:
    - Incremental mode (default): generate documentation only for files changed
      between the given Git refs.
    - Full mode (--all): generate documentation for all relevant files in the repo.

    For each candidate file, the command:
    1. Builds a context bundle.
    2. Constructs a prompt.
    3. Computes a cache key.
    4. Reuses cached output if available.
    5. Otherwise generates and saves fresh documentation.

    After per-file documentation is available, the command optionally combines
    those file-level docs into a repository-level Markdown summary and writes it
    to <repo>/.autodoc/REPOSITORY.md.

    Args:
        repo: Path to the target repository.
        base: Base Git ref for incremental comparison.
        head: Head Git ref for incremental comparison.
        model: Model identifier used for documentation generation.
        limit: Optional maximum number of files to process.
        all_files: If True, process all relevant files instead of only changed ones.

    Raises:
        typer.Exit: Exits with code 1 for fatal setup/file gathering errors,
        or code 0 when there is simply nothing to process.
    """
    repo_path = Path(repo).resolve()

    # Ensure the target path is a valid Git repository before doing anything else.
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

    # Optionally restrict the number of files processed for testing/cost control.
    if limit is not None:
        candidates = candidates[:limit]

    if not candidates:
        console.print("[yellow]No relevant files found.[/yellow]")
        raise typer.Exit(code=0)

    # Create a summary table for terminal output.
    summary = Table(title="Autodoc Generation Summary")
    summary.add_column("File")
    summary.add_column("Status")
    summary.add_column("Reason")

    generated_count = 0
    cached_count = 0
    failed_count = 0

    # Store (source file path, generated markdown path) for repo-level documentation later.
    per_file_markdown_paths: List[Tuple[str, Path]] = []

    for item in candidates:
        try:
            # Build the full context required for generating documentation.
            bundle = build_context_bundle(
                repo_path,
                base,
                head,
                item.path,
                include_diff=not all_files,
            )
            prompt_text = build_prompt(bundle)

            # Compute a deterministic cache key based on the generation inputs.
            cache_key = compute_cache_key(
                target_file=item.path,
                prompt_text=prompt_text,
                model_name=model,
                prompt_version=PROMPT_VERSION,
            )

            # Reuse cached documentation if it already exists.
            if cache_exists(repo_path, cache_key):
                md_path, _ = get_cache_paths(repo_path, cache_key)
                summary.add_row(item.path, "cached", str(md_path))
                cached_count += 1
                per_file_markdown_paths.append((item.path, md_path))
                continue

            # Generate fresh documentation if no cached entry exists.
            markdown = generate_documentation(prompt_text, item.path)
            md_path, _ = save_cache_entry(
                repo=repo_path,
                cache_key=cache_key,
                markdown=markdown,
                source_file=item.path,
                model_name=model,
                prompt_version=PROMPT_VERSION,
                base_ref=base,
                head_ref=head,
            )

            summary.add_row(item.path, "generated", str(md_path))
            generated_count += 1
            per_file_markdown_paths.append((item.path, md_path))

        except Exception as e:
            # Record per-file failure without killing the whole run.
            summary.add_row(item.path, "failed", str(e))
            failed_count += 1

    console.print(summary)

    # Generate repository-level documentation if we have any per-file docs.
    if per_file_markdown_paths:
        repo_readme = read_repo_readme(repo_path)

        file_docs: List[Tuple[str, str]] = []
        for path_str, md_path in per_file_markdown_paths:
            try:
                content = md_path.read_text(encoding="utf-8")
            except Exception:
                continue

            # Truncate very large file docs to keep the repository prompt bounded.
            max_chars = 4000
            if len(content) > max_chars:
                content = content[:max_chars] + "\n\n...[truncated]...\n"

            file_docs.append((path_str, content))

        if file_docs:
            # Build and generate the repository-level documentation.
            repo_prompt = build_repo_prompt(
                repo_name=repo_path.name,
                readme_content=repo_readme,
                file_docs=file_docs,
            )
            repo_markdown = generate_repo_documentation(repo_prompt)

            # Save repository-level documentation to the .autodoc directory.
            repo_doc_dir = repo_path / AUTODOC_DIR
            repo_doc_dir.mkdir(parents=True, exist_ok=True)
            repo_doc_path = repo_doc_dir / "REPOSITORY.md"
            repo_doc_path.write_text(repo_markdown, encoding="utf-8")

            console.print(f"\n[bold]Repository documentation written to:[/bold] {repo_doc_path}")

    console.print(
        f"\n[bold]Done.[/bold] generated={generated_count}, cached={cached_count}, failed={failed_count}"
    )


if __name__ == "__main__":
    app()