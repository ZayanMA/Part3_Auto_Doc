from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional


class ChangedFile(BaseModel):
    path: str
    status: str  # A, M, D, R...


class ContextBundle(BaseModel):
    target_file: str
    target_content: str
    diff_text: str = ""
    readme_content: str = ""
    nearby_files: List[str] = Field(default_factory=list)
    nearby_contents: List[str] = Field(default_factory=list)


class CacheMetadata(BaseModel):
    source_file: str
    cache_key: str
    output_markdown_path: str
    output_metadata_path: str
    model_name: str
    prompt_version: str
    generated_at_utc: str
    base_ref: str
    head_ref: str


class GenerationResult(BaseModel):
    source_file: str
    cache_key: str
    used_cache: bool
    markdown_path: Path
    metadata_path: Path
    status: str  # generated / cached / skipped / failed
    reason: Optional[str] = None