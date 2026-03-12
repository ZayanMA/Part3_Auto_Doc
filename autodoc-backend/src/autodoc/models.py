from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from dataclasses import dataclass, field
from pathlib import Path

from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class UnitContextBundle:
    unit_name: str
    unit_slug: str
    unit_kind: str
    unit_root: str
    readme_content: str
    files: List[str]
    # (path, content)
    file_contents: List[Tuple[str, str]]
    # (path, diff)
    diffs: List[Tuple[str, str]]

@dataclass
class DocumentationUnit:
    name: str                  # e.g. "Authentication"
    slug: str                  # e.g. "authentication"
    kind: str                  # e.g. "module", "api", "config", "overview"
    root: str                  # e.g. "src/auth"
    files: list[str] = field(default_factory=list)


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