from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class UnitContextBundle:
    unit_name: str
    unit_slug: str
    unit_kind: str
    unit_root: str
    readme_content: str
    existing_unit_doc: str
    files: List[str]
    file_contents: List[tuple[str, str]]   # selected fulltext
    diffs: List[tuple[str, str]]           # only changed files
    neighbour_summaries: List[tuple[str, str]] = field(default_factory=list)
    repo_manifest: str = ""
    changed_symbols: List[str] = field(default_factory=list)
    scored_doc_sections: List[tuple[str, str]] = field(default_factory=list)


@dataclass
class JobUsageSummary:
    input_tokens: int = 0
    output_tokens: int = 0
    units_processed: int = 0
    units_cached: int = 0

    def add(self, input_t: int, output_t: int) -> "JobUsageSummary":
        return JobUsageSummary(
            input_tokens=self.input_tokens + input_t,
            output_tokens=self.output_tokens + output_t,
            units_processed=self.units_processed + 1,
            units_cached=self.units_cached,
        )

    def add_cached(self) -> "JobUsageSummary":
        return JobUsageSummary(
            input_tokens=self.input_tokens,
            output_tokens=self.output_tokens,
            units_processed=self.units_processed,
            units_cached=self.units_cached + 1,
        )


@dataclass
class GenerationUsage:
    model: str
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float


@dataclass
class DocumentationUnit:
    name: str
    slug: str
    kind: str
    root: str
    files: list[str] = field(default_factory=list)
    name_source: str = "heuristic"  # "heuristic" | "llm"


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
    mode: str = "full"
    routing_reason: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0.0
    last_accessed_utc: str = ""


class GenerationResult(BaseModel):
    source_file: str
    cache_key: str
    used_cache: bool
    markdown_path: Path
    metadata_path: Path
    status: str  # generated / cached / skipped / failed
    reason: Optional[str] = None
