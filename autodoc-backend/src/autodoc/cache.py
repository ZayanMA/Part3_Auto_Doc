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
) -> tuple[Path, Path]:
    md_path, meta_path = get_cache_paths(repo, cache_key)

    md_path.write_text(markdown, encoding="utf-8")

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

    meta_path.write_text(
        json.dumps(metadata.model_dump(), indent=2),
        encoding="utf-8",
    )

    return md_path, meta_path