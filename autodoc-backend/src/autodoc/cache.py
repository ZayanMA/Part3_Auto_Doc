from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from autodoc.models import CacheMetadata


AUTODOC_DIR = ".autodoc"
CACHE_DIR = "cache"


def ensure_cache_dirs(repo: Path) -> Path:
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
    material = "\n".join([
        f"target_file={target_file}",
        f"model_name={model_name}",
        f"prompt_version={prompt_version}",
        prompt_text,
    ])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def compute_incremental_cache_key(
    unit_slug: str,
    changed_files_content: dict[str, str],
    existing_doc: str,
    model_name: str,
    prompt_version: str,
) -> str:
    """Cache key for patch mode — hashes only changed files + existing doc."""
    sorted_hashes = sorted(
        f"{path}:{hashlib.sha256(content.encode()).hexdigest()}"
        for path, content in changed_files_content.items()
    )
    existing_hash = hashlib.sha256(existing_doc.encode()).hexdigest()
    material = "\n".join([
        f"unit_slug={unit_slug}",
        f"model_name={model_name}",
        f"prompt_version={prompt_version}",
        f"existing_doc={existing_hash}",
        *sorted_hashes,
    ])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def get_cache_paths(repo: Path, cache_key: str) -> tuple[Path, Path]:
    cache_root = ensure_cache_dirs(repo)
    md_path = cache_root / f"{cache_key}.md"
    meta_path = cache_root / f"{cache_key}.json"
    return md_path, meta_path


def cache_exists(repo: Path, cache_key: str) -> bool:
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
    mode: str = "full",
    routing_reason: str = "",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    estimated_cost_usd: float = 0.0,
) -> tuple[Path, Path]:
    md_path, meta_path = get_cache_paths(repo, cache_key)

    md_path.write_text(markdown, encoding="utf-8")

    now = datetime.now(timezone.utc).isoformat()
    metadata = CacheMetadata(
        source_file=source_file,
        cache_key=cache_key,
        output_markdown_path=str(md_path),
        output_metadata_path=str(meta_path),
        model_name=model_name,
        prompt_version=prompt_version,
        generated_at_utc=now,
        base_ref=base_ref,
        head_ref=head_ref,
        mode=mode,
        routing_reason=routing_reason,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        estimated_cost_usd=estimated_cost_usd,
        last_accessed_utc=now,
    )

    meta_path.write_text(
        json.dumps(metadata.model_dump(), indent=2),
        encoding="utf-8",
    )

    return md_path, meta_path


def prune_cache(repo: Path, max_age_days: int) -> int:
    """Delete cache entries older than max_age_days. Returns count deleted."""
    cache_root = repo / AUTODOC_DIR / CACHE_DIR
    if not cache_root.exists():
        return 0

    now = datetime.now(timezone.utc)
    deleted = 0

    for meta_file in cache_root.glob("*.json"):
        try:
            data = json.loads(meta_file.read_text(encoding="utf-8"))
            generated_at = datetime.fromisoformat(data.get("generated_at_utc", ""))
            age_days = (now - generated_at).days
            if age_days > max_age_days:
                md_file = meta_file.with_suffix(".md")
                meta_file.unlink(missing_ok=True)
                md_file.unlink(missing_ok=True)
                deleted += 1
        except Exception:
            continue

    return deleted


def append_changelog_entry(
    doc_path: Path,
    mode: str,
    model: str,
    base_ref: str,
    head_ref: str,
) -> None:
    """Append an HTML comment changelog entry to a stable doc file."""
    if not doc_path.exists():
        return
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = f"\n<!-- autodoc: {now} mode={mode} model={model} base={base_ref} head={head_ref} -->\n"
    try:
        with open(doc_path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass
