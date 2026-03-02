from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from autodoc.models import CacheMetadata


# Root folder inside the target repository used by this tool.
AUTODOC_DIR = ".autodoc"

# Subdirectory where cached documentation artifacts are stored.
CACHE_DIR = "cache"


def ensure_cache_dirs(repo: Path) -> Path:
    """
    Ensure the cache directory exists inside the target repository.

    Args:
        repo: Path to the target repository root.

    Returns:
        Path to the cache directory, e.g. <repo>/.autodoc/cache.

    Notes:
        - Creates parent directories if they do not already exist.
        - Does not fail if the directory is already present.
    """
    cache_root = repo / AUTODOC_DIR / CACHE_DIR
    cache_root.mkdir(parents=True, exist_ok=True)
    return cache_root


def compute_cache_key(
    *,
    target_file: str,
    prompt_text: str,
    model_name: str,
    prompt_version: str,
) -> str:
    """
    Compute a deterministic cache key for a documentation generation request.

    The cache key is derived from the key inputs that affect generated output.
    If any of these inputs change, the resulting hash changes too, which forces
    regeneration instead of reusing stale cached documentation.

    Args:
        target_file: Path of the source file being documented.
        prompt_text: Full prompt sent to the LLM.
        model_name: Name/identifier of the model used for generation.
        prompt_version: Version string for the prompt template.

    Returns:
        A SHA-256 hex digest string that uniquely identifies this generation input.
    """
    material = "\n".join(
        [
            f"target_file={target_file}",
            f"model_name={model_name}",
            f"prompt_version={prompt_version}",
            prompt_text,
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def get_cache_paths(repo: Path, cache_key: str) -> tuple[Path, Path]:
    """
    Get the output file paths for a given cache key.

    Args:
        repo: Path to the target repository root.
        cache_key: Unique hash key for the generation request.

    Returns:
        A tuple of:
        - markdown path (<cache_key>.md)
        - metadata path (<cache_key>.json)
    """
    cache_root = ensure_cache_dirs(repo)
    md_path = cache_root / f"{cache_key}.md"
    meta_path = cache_root / f"{cache_key}.json"
    return md_path, meta_path


def cache_exists(repo: Path, cache_key: str) -> bool:
    """
    Check whether a complete cached documentation entry already exists.

    A cache entry is considered valid only if both the generated Markdown file
    and the corresponding metadata JSON file are present.

    Args:
        repo: Path to the target repository root.
        cache_key: Unique hash key for the generation request.

    Returns:
        True if both cache files exist, otherwise False.
    """
    md_path, meta_path = get_cache_paths(repo, cache_key)
    return md_path.exists() and meta_path.exists()


def save_cache_entry(
    *,
    repo: Path,
    cache_key: str,
    markdown: str,
    source_file: str,
    model_name: str,
    prompt_version: str,
    base_ref: str,
    head_ref: str,
) -> tuple[Path, Path]:
    """
    Save generated documentation and its metadata to the local cache.

    This writes:
    - the generated Markdown documentation
    - a JSON metadata file describing how and when it was produced

    Args:
        repo: Path to the target repository root.
        cache_key: Unique hash key for the generation request.
        markdown: Generated Markdown documentation content.
        source_file: Source file for which documentation was generated.
        model_name: Name/identifier of the model used for generation.
        prompt_version: Version string for the prompt template.
        base_ref: Base Git ref used for the change comparison.
        head_ref: Head Git ref used for the change comparison.

    Returns:
        A tuple of:
        - path to the saved Markdown file
        - path to the saved metadata JSON file
    """
    md_path, meta_path = get_cache_paths(repo, cache_key)

    # Save the generated Markdown documentation.
    md_path.write_text(markdown, encoding="utf-8")

    # Build a structured metadata record for traceability and reuse.
    metadata = CacheMetadata(
        source_file=source_file,
        cache_key=cache_key,
        output_markdown_path=str(md_path),
        output_metadata_path=str(meta_path),
        model_name=model_name,
        prompt_version=prompt_version,
        generated_at_utc=datetime.now(timezone.utc).isoformat(),
        base_ref=base_ref,
        head_ref=head_ref,
    )

    # Save metadata alongside the Markdown output as formatted JSON.
    meta_path.write_text(
        json.dumps(metadata.model_dump(), indent=2),
        encoding="utf-8",
    )

    return md_path, meta_path