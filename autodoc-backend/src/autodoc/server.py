from __future__ import annotations

import asyncio
import io
import os
import queue as _queue
import shutil
import subprocess
import tempfile
import threading
import uuid
import zipfile
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from autodoc.prompts import PROMPT_VERSION

app = FastAPI(title="AutoDoc API", version=PROMPT_VERSION)

# ─── CORS ─────────────────────────────────────────────────────────────────────

_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    os.environ.get("AUTODOC_DEMO_ORIGIN", ""),
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in _CORS_ORIGINS if o],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── State ────────────────────────────────────────────────────────────────────

_jobs: dict[str, "JobRecord"] = {}
_jobs_lock = threading.Lock()

_job_queues: dict[str, _queue.Queue] = {}
_job_queues_lock = threading.Lock()

_bearer = HTTPBearer(auto_error=False)


# ─── Auth ─────────────────────────────────────────────────────────────────────

def _check_auth(credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer)) -> None:
    api_key = os.environ.get("AUTODOC_API_KEY")
    if not api_key:
        return  # auth disabled when env var is unset
    if credentials is None or credentials.credentials != api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


# ─── Models ───────────────────────────────────────────────────────────────────

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class GenerateRequest(BaseModel):
    repo_full_name: str          # "owner/repo" — cloned by the server
    github_token: str            # GitHub token used to clone (never logged)
    base: str = "HEAD~1"
    head: str = "HEAD"
    model: Optional[str] = None
    all_files: bool = False
    config_path: Optional[str] = None


class DemoGenerateRequest(BaseModel):
    git_url: str
    base: str = "HEAD~1"
    head: str = "HEAD"
    all_files: bool = False
    git_token: Optional[str] = None
    mock_generation: bool = False


class UnitResult(BaseModel):
    slug: str
    name: str
    kind: str
    markdown: str
    status: str
    prev_markdown: Optional[str] = None
    quality: Optional[dict] = None


class JobRecord(BaseModel):
    job_id: str
    status: JobStatus
    created_at: str
    finished_at: Optional[str] = None
    phase: str = "pending"
    phase_message: Optional[str] = None
    total_units: int = 0
    done_units: int = 0
    units: Optional[list[UnitResult]] = None
    repo_doc: Optional[str] = None
    error: Optional[str] = None


class JobEvent(BaseModel):
    event: str        # unit_started | unit_routed | llm_start | llm_done | quality_checked |
                      # unit_cache_hit | unit_done | unit_failed | job_started | job_done | job_failed
    job_id: str
    slug: Optional[str] = None
    name: Optional[str] = None
    kind: Optional[str] = None
    status: Optional[str] = None
    phase: Optional[str] = None
    phase_message: Optional[str] = None
    total_units: Optional[int] = None
    done_units: Optional[int] = None
    units: Optional[list] = None
    repo_doc: Optional[str] = None
    error: Optional[str] = None
    # Fine-grained fields (claw-code streaming pattern)
    model: Optional[str] = None
    mode: Optional[str] = None
    routing_reason: Optional[str] = None
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None
    quality_score: Optional[float] = None


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_job(job_id: str, **kwargs) -> None:
    with _jobs_lock:
        record = _jobs[job_id]
        updated = record.model_copy(update=kwargs)
        _jobs[job_id] = updated


def _set_job_phase(job_id: str, phase: str, message: Optional[str] = None) -> None:
    _set_job(job_id, phase=phase, phase_message=message)
    _emit_event(
        job_id,
        JobEvent(
            event="job_phase",
            job_id=job_id,
            phase=phase,
            phase_message=message,
        ),
    )


def _build_mock_markdown(unit_name: str, unit_slug: str, unit_kind: str, files: list[str]) -> str:
    file_lines = "\n".join(f"- `{path}`" for path in files[:12]) or "- No files detected"
    return (
        f"# {unit_name}\n\n"
        "## Overview\n"
        f"This is deterministic mock documentation for `{unit_slug}` used to test the demo flow without consuming LLM credits.\n\n"
        "## Responsibilities\n"
        f"This unit is classified as `{unit_kind}` and groups related source files for documentation.\n\n"
        "## Key APIs & Interfaces\n"
        "Mock mode does not infer real APIs; this section confirms the rendering path works end to end.\n\n"
        "## Configuration & Data\n"
        "No synthetic configuration is generated in mock mode.\n\n"
        "## Dependencies\n"
        "Dependency analysis is skipped for mock output.\n\n"
        "## Usage Notes\n"
        "Use mock generation to validate job progress, polling, SSE, and document rendering without external API calls.\n\n"
        "## Files\n"
        f"{file_lines}\n"
    )


def _build_mock_repo_doc(repo_name: str, unit_results: list[UnitResult]) -> str:
    section_lines = "\n".join(f"- `{unit.name}` (`{unit.kind}`)" for unit in unit_results) or "- No units generated"
    return (
        f"# Repository Overview: {repo_name}\n\n"
        "This is deterministic mock repository documentation generated without external LLM calls.\n\n"
        "## Included Units\n"
        f"{section_lines}\n\n"
        "## Usage Notes\n"
        "This output is intended for testing the demo website, backend job lifecycle, and document rendering paths.\n"
    )


def _emit_event(job_id: str, event: JobEvent) -> None:
    with _job_queues_lock:
        q = _job_queues.get(job_id)
    if q is not None:
        q.put(event)


def _schedule_queue_cleanup(job_id: str) -> None:
    def _cleanup() -> None:
        import time
        time.sleep(300)  # 5 minutes
        with _job_queues_lock:
            _job_queues.pop(job_id, None)

    t = threading.Thread(target=_cleanup, daemon=True)
    t.start()


# ─── Clone helpers ────────────────────────────────────────────────────────────

def _clone_github_repo(token: str, full_name: str, tmpdir: str) -> None:
    clone_url = f"https://x-access-token:{token}@github.com/{full_name}.git"
    try:
        subprocess.run(
            ["git", "clone", clone_url, tmpdir],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Failed to clone {full_name} (git exit {exc.returncode})"
        ) from None


def _clone_repo_url(url: str, token: Optional[str], tmpdir: str) -> None:
    if token:
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        authed = parsed._replace(netloc=f"oauth2:{token}@{parsed.netloc}")
        clone_url = urlunparse(authed)
    else:
        clone_url = url
    try:
        subprocess.run(
            ["git", "clone", clone_url, tmpdir],
            check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f"Failed to clone {url} (git exit {exc.returncode})"
        ) from None


# ─── Core processing pipeline ─────────────────────────────────────────────────

def _run_processing(
    job_id: str,
    repo_path,  # pathlib.Path
    base: str,
    head: str,
    all_files: bool,
    cfg_file=None,
    model: Optional[str] = None,
    *,
    preflight_llm: bool = True,
    mock_generation: bool = False,
) -> None:
    """Shared processing pipeline — emits events to the job queue."""
    from pathlib import Path
    from autodoc.cache import (
        AUTODOC_DIR, cache_exists, compute_cache_key, get_cache_paths,
        save_cache_entry, append_changelog_entry,
    )
    from autodoc.config import load_config
    from autodoc.context import (
        read_repo_readme, group_files_into_units, merge_small_groups,
        merge_by_import_coupling, make_units_from_groups, build_unit_context_bundle,
        apply_unit_overrides, collapse_homogeneous_siblings, verify_units_relevance,
        enrich_unit_names,
    )
    from autodoc.repo_index import (
        load_index, save_index, build_repo_index, diff_indices,
        impacted_units, utc_now_iso, build_import_graph,
    )
    from autodoc.filters import get_all_relevant_files_git, is_probably_text_file
    from autodoc.git_utils import ensure_git_repo, get_changed_files
    from autodoc.llm import generate_documentation, generate_repo_documentation
    from autodoc.manifest import build_repo_manifest, render_manifest
    from autodoc.prompts import build_repo_prompt, build_unit_prompt, build_unit_patch_prompt
    from autodoc.router import route_model
    from autodoc.quality import evaluate_unit
    from autodoc.session import PersistedSession, save_session

    cfg = load_config(repo_path, cfg_file)
    if model:
        cfg.fast_model = model
        cfg.smart_model = model

    ensure_git_repo(repo_path)

    _set_job_phase(job_id, "discovering_files", "Discovering relevant files")
    all_candidates = get_all_relevant_files_git(repo_path)
    all_paths = [c.path for c in all_candidates]

    _set_job_phase(job_id, "grouping_units", "Grouping files into documentation units")
    raw_groups = group_files_into_units(all_paths)
    raw_groups = apply_unit_overrides(raw_groups, cfg.unit_overrides, all_paths)
    raw_groups = collapse_homogeneous_siblings(raw_groups)

    try:
        _set_job_phase(job_id, "building_graph", "Building repository import graph")
        _raw_imports, _resolved = build_import_graph(repo_path, all_paths)
        deps: dict[str, set[str]] = {k: set(v) for k, v in _resolved.items()}
    except Exception:
        deps = {}

    groups = merge_by_import_coupling(raw_groups, deps)
    groups = merge_small_groups(groups, min_files=cfg.min_files_per_unit)
    all_units = make_units_from_groups(groups)
    if preflight_llm:
        _set_job_phase(job_id, "naming_units", "Naming documentation units")
        all_units = enrich_unit_names(all_units, repo_path, cfg.fast_model)
        _set_job_phase(job_id, "filtering_units", "Filtering units for relevance")
        all_units = verify_units_relevance(all_units, repo_path, cfg.fast_model)

    if not all_units:
        _set_job(
            job_id,
            status=JobStatus.DONE,
            finished_at=_utc_now(),
            phase="done",
            phase_message="No documentation units found",
            units=[],
            repo_doc=None,
        )
        _emit_event(
            job_id,
            JobEvent(
                event="job_done",
                job_id=job_id,
                phase="done",
                phase_message="No documentation units found",
                units=[],
                total_units=0,
                done_units=0,
            ),
        )
        _schedule_queue_cleanup(job_id)
        return

    repo_manifest_obj = build_repo_manifest(repo_path, all_units, all_paths)
    repo_manifest_text = render_manifest(repo_manifest_obj)

    changed_files_set: set[str] = set()
    if all_files:
        changed_files_set = set(all_paths)
    else:
        changed = get_changed_files(repo_path, base, head)
        changed_files_set = {
            c.path for c in changed
            if c.status != "D" and is_probably_text_file(c.path)
        }

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

    total = len(units_to_run)
    _set_job(
        job_id,
        phase="generating",
        phase_message="Generating documentation units",
        total_units=total,
        done_units=0,
    )
    _emit_event(
        job_id,
        JobEvent(
            event="job_started",
            job_id=job_id,
            phase="generating",
            phase_message="Generating documentation units",
            total_units=total,
            done_units=0,
        ),
    )

    # Persist session to disk at job start (survives server restarts)
    session = PersistedSession(
        job_id=job_id,
        repo_name=repo_path.name,
        base_ref=base,
        head_ref=head,
        status="running",
        created_at=_utc_now(),
        finished_at=None,
        total_units=total,
        units_completed=[],
        units_failed=[],
        total_input_tokens=0,
        total_output_tokens=0,
        total_cost_usd=0.0,
        fast_model=cfg.fast_model,
        smart_model=cfg.smart_model,
    )
    save_session(session)

    units_dir = repo_path / AUTODOC_DIR / "units"
    units_dir.mkdir(parents=True, exist_ok=True)

    unit_results: list[UnitResult] = []
    done_count = 0
    _job_total_tokens = 0
    _job_total_cost = 0.0

    for unit in units_to_run:
        stable_path = units_dir / f"{unit.slug}.md"

        _emit_event(job_id, JobEvent(
            event="unit_started", job_id=job_id,
            slug=unit.slug, name=unit.name, kind=unit.kind,
            total_units=total, done_units=done_count,
        ))

        try:
            bundle = build_unit_context_bundle(
                repo_path, base, head, unit,
                include_diff=not all_files,
                changed_files=changed_files_set,
                max_file_chars=cfg.max_file_chars,
                max_files_fulltext=cfg.max_files_fulltext,
                token_budget=cfg.token_budget,
                all_units=all_units,
                deps=deps,
                repo_manifest=repo_manifest_text,
            )
            decision = route_model(unit, changed_files_set, bundle.diffs, bundle.existing_unit_doc, cfg)

            # Emit routing decision (claw-code: RoutedMatch with score + reason)
            _emit_event(job_id, JobEvent(
                event="unit_routed", job_id=job_id,
                slug=unit.slug, name=unit.name, kind=unit.kind,
                model=decision.model, mode=decision.mode,
                routing_reason=decision.reason,
                total_units=total, done_units=done_count,
            ))

            if decision.mode == "patch" and bundle.diffs:
                prompt_text = build_unit_patch_prompt(bundle)
                changed_files_content = {p: c for p, c in bundle.file_contents if p in changed_files_set}
                from autodoc.cache import compute_incremental_cache_key
                cache_key = compute_incremental_cache_key(
                    unit.slug, changed_files_content, bundle.existing_unit_doc,
                    decision.model, PROMPT_VERSION,
                )
            else:
                prompt_text = build_unit_prompt(bundle)
                cache_key = compute_cache_key(
                    target_file=unit.slug,
                    prompt_text=prompt_text,
                    model_name=decision.model,
                    prompt_version=PROMPT_VERSION,
                )

            unit_tokens: int = 0
            unit_cost: float = 0.0

            if mock_generation:
                markdown = _build_mock_markdown(unit.name, unit.slug, unit.kind, unit.files)
                status_label = "mock"
            elif cache_exists(repo_path, cache_key):
                md_path, _ = get_cache_paths(repo_path, cache_key)
                markdown = md_path.read_text(encoding="utf-8")
                status_label = "cached"
                _emit_event(job_id, JobEvent(
                    event="unit_cache_hit", job_id=job_id,
                    slug=unit.slug, name=unit.name,
                    total_units=total, done_units=done_count,
                ))
            else:
                _emit_event(job_id, JobEvent(
                    event="llm_start", job_id=job_id,
                    slug=unit.slug, model=decision.model, mode=decision.mode,
                    total_units=total, done_units=done_count,
                ))
                markdown, usage = generate_documentation(prompt_text, unit.slug, model=decision.model)
                unit_tokens = usage.prompt_tokens + usage.completion_tokens
                unit_cost = usage.estimated_cost_usd
                _job_total_tokens += unit_tokens
                _job_total_cost += unit_cost
                _emit_event(job_id, JobEvent(
                    event="llm_done", job_id=job_id,
                    slug=unit.slug, model=decision.model,
                    tokens_used=unit_tokens, cost_usd=unit_cost,
                    total_units=total, done_units=done_count,
                ))
                md_path, _ = save_cache_entry(
                    repo=repo_path, cache_key=cache_key, markdown=markdown,
                    source_file=unit.root, model_name=decision.model,
                    prompt_version=PROMPT_VERSION, base_ref=base, head_ref=head,
                    mode=decision.mode, routing_reason=decision.reason,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    estimated_cost_usd=usage.estimated_cost_usd,
                )
                append_changelog_entry(stable_path, decision.mode, decision.model, base, head)
                status_label = decision.mode

            try:
                stable_path.write_text(markdown, encoding="utf-8")
            except Exception:
                pass

            quality_dict: Optional[dict] = None
            quality_score: Optional[float] = None
            try:
                report = evaluate_unit(unit.slug, unit.name, unit.kind, markdown, unit.files, repo_path)
                quality_dict = report.__dict__
                quality_score = report.overall_score
                _emit_event(job_id, JobEvent(
                    event="quality_checked", job_id=job_id,
                    slug=unit.slug, name=unit.name,
                    quality_score=quality_score,
                    total_units=total, done_units=done_count,
                ))
            except Exception:
                pass

            prev_md = bundle.existing_unit_doc if status_label == "patch" and bundle.existing_unit_doc.strip() else None
            unit_result = UnitResult(
                slug=unit.slug, name=unit.name, kind=unit.kind,
                markdown=markdown, status=status_label,
                prev_markdown=prev_md,
                quality=quality_dict,
            )
            unit_results.append(unit_result)
            done_count += 1
            _set_job(job_id, done_units=done_count)

            # Update persisted session
            session = PersistedSession(
                job_id=session.job_id,
                repo_name=session.repo_name,
                base_ref=session.base_ref,
                head_ref=session.head_ref,
                status="running",
                created_at=session.created_at,
                finished_at=None,
                total_units=total,
                units_completed=session.units_completed + [unit.slug],
                units_failed=session.units_failed,
                total_input_tokens=_job_total_tokens,
                total_output_tokens=0,
                total_cost_usd=_job_total_cost,
                fast_model=session.fast_model,
                smart_model=session.smart_model,
            )
            save_session(session)

            _emit_event(job_id, JobEvent(
                event="unit_done", job_id=job_id,
                slug=unit.slug, name=unit.name, kind=unit.kind,
                status=status_label,
                model=decision.model, mode=decision.mode,
                tokens_used=unit_tokens if unit_tokens else None,
                cost_usd=unit_cost if unit_cost else None,
                quality_score=quality_score,
                total_units=total, done_units=done_count,
            ))

        except Exception as e:
            unit_result = UnitResult(
                slug=unit.slug, name=unit.name, kind=unit.kind,
                markdown="", status=f"failed: {e}",
            )
            unit_results.append(unit_result)
            done_count += 1
            _set_job(job_id, done_units=done_count)

            session = PersistedSession(
                job_id=session.job_id,
                repo_name=session.repo_name,
                base_ref=session.base_ref,
                head_ref=session.head_ref,
                status="running",
                created_at=session.created_at,
                finished_at=None,
                total_units=total,
                units_completed=session.units_completed,
                units_failed=session.units_failed + [unit.slug],
                total_input_tokens=_job_total_tokens,
                total_output_tokens=0,
                total_cost_usd=_job_total_cost,
                fast_model=session.fast_model,
                smart_model=session.smart_model,
            )
            save_session(session)

            _emit_event(job_id, JobEvent(
                event="unit_failed", job_id=job_id,
                slug=unit.slug, name=unit.name, kind=unit.kind,
                status=f"failed: {e}",
                total_units=total, done_units=done_count,
                error=str(e),
            ))

    # Repo overview
    repo_markdown: Optional[str] = None
    repo_readme = read_repo_readme(repo_path)
    unit_docs = []
    for p in sorted(units_dir.glob("*.md")):
        try:
            content = p.read_text(encoding="utf-8")
        except Exception:
            continue
        max_chars = cfg.token_budget * 4
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n...[truncated]...\n"
        unit_docs.append((p.stem, content))

    if unit_docs:
        _set_job_phase(job_id, "finalizing", "Building repository overview")
        if mock_generation:
            repo_markdown = _build_mock_repo_doc(repo_path.name, unit_results)
        else:
            unit_index = [(u.name, u.slug) for u in unit_results]
            repo_prompt = build_repo_prompt(
                repo_name=repo_path.name,
                readme_content=repo_readme,
                file_docs=unit_docs,
                unit_index=unit_index,
            )
            repo_markdown = generate_repo_documentation(repo_prompt, model=cfg.smart_model)
        repo_doc_path = repo_path / AUTODOC_DIR / "REPOSITORY.md"
        repo_doc_path.write_text(repo_markdown, encoding="utf-8")

    new_idx.updated_at_utc = utc_now_iso()
    save_index(repo_path, new_idx)

    finished_ts = _utc_now()
    successful_units = [u for u in unit_results if not u.status.startswith("failed")]
    if total > 0 and not successful_units:
        failed_reasons = [
            f"{u.name}: {u.status.removeprefix('failed: ').strip()}"
            for u in unit_results
            if u.status.startswith("failed:")
        ]
        aggregate_error = "All documentation units failed to generate"
        if failed_reasons:
            aggregate_error = f"{aggregate_error}. " + " | ".join(failed_reasons[:3])
        _set_job(
            job_id,
            status=JobStatus.FAILED,
            finished_at=finished_ts,
            phase="failed",
            phase_message="All documentation units failed to generate",
            units=unit_results,
            repo_doc=None,
            error=aggregate_error,
        )
        _emit_event(
            job_id,
            JobEvent(
                event="job_failed",
                job_id=job_id,
                phase="failed",
                phase_message="All documentation units failed to generate",
                units=[u.model_dump() for u in unit_results],
                total_units=total,
                done_units=done_count,
                error=aggregate_error,
            ),
        )
        _schedule_queue_cleanup(job_id)
        return

    _set_job(
        job_id,
        status=JobStatus.DONE,
        finished_at=finished_ts,
        phase="done",
        phase_message="Documentation generation complete",
        units=unit_results,
        repo_doc=repo_markdown,
    )

    # Finalize persisted session
    session = PersistedSession(
        job_id=session.job_id,
        repo_name=session.repo_name,
        base_ref=session.base_ref,
        head_ref=session.head_ref,
        status="completed",
        created_at=session.created_at,
        finished_at=finished_ts,
        total_units=total,
        units_completed=session.units_completed,
        units_failed=session.units_failed,
        total_input_tokens=_job_total_tokens,
        total_output_tokens=0,
        total_cost_usd=_job_total_cost,
        fast_model=session.fast_model,
        smart_model=session.smart_model,
    )
    save_session(session)

    _emit_event(job_id, JobEvent(
        event="job_done", job_id=job_id,
        phase="done",
        phase_message="Documentation generation complete",
        units=[u.model_dump() for u in unit_results],
        repo_doc=repo_markdown,
        total_units=total, done_units=done_count,
        tokens_used=_job_total_tokens,
        cost_usd=_job_total_cost,
    ))
    _schedule_queue_cleanup(job_id)


# ─── Background jobs ──────────────────────────────────────────────────────────

def run_generate_job(job_id: str, req: GenerateRequest) -> None:
    from autodoc.session import PersistedSession, save_session, load_session
    _set_job(job_id, status=JobStatus.RUNNING, phase="cloning", phase_message="Cloning repository")
    tmpdir: Optional[str] = None
    try:
        from pathlib import Path
        tmpdir = tempfile.mkdtemp(prefix="autodoc_")
        _clone_github_repo(req.github_token, req.repo_full_name, tmpdir)
        repo_path = Path(tmpdir)
        cfg_file = Path(req.config_path) if req.config_path else None
        _run_processing(job_id, repo_path, req.base, req.head, req.all_files, cfg_file, req.model)
    except Exception as e:
        finished_ts = _utc_now()
        _set_job(job_id, status=JobStatus.FAILED, finished_at=finished_ts, phase="failed", phase_message="Job failed", error=str(e))
        _emit_event(job_id, JobEvent(event="job_failed", job_id=job_id, phase="failed", phase_message="Job failed", error=str(e)))
        # Persist failure to session store
        existing = load_session(job_id)
        if existing:
            from dataclasses import replace as _replace
            save_session(_replace(existing, status="failed", finished_at=finished_ts, error=str(e)))
        _schedule_queue_cleanup(job_id)
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


def run_demo_generate_job(job_id: str, req: DemoGenerateRequest) -> None:
    _set_job(job_id, status=JobStatus.RUNNING, phase="cloning", phase_message="Cloning repository")
    tmpdir: Optional[str] = None
    try:
        from pathlib import Path
        tmpdir = tempfile.mkdtemp(prefix="autodoc_demo_")
        _clone_repo_url(req.git_url, req.git_token, tmpdir)
        repo_path = Path(tmpdir)
        _run_processing(
            job_id,
            repo_path,
            req.base,
            req.head,
            req.all_files,
            preflight_llm=not req.mock_generation,
            mock_generation=req.mock_generation,
        )
    except Exception as e:
        _set_job(job_id, status=JobStatus.FAILED, finished_at=_utc_now(), phase="failed", phase_message="Job failed", error=str(e))
        _emit_event(job_id, JobEvent(event="job_failed", job_id=job_id, phase="failed", phase_message="Job failed", error=str(e)))
        _schedule_queue_cleanup(job_id)
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


def run_demo_zip_job(job_id: str, zip_bytes: bytes, mock_generation: bool = False) -> None:
    _set_job(job_id, status=JobStatus.RUNNING, phase="extracting", phase_message="Extracting ZIP archive")
    tmpdir: Optional[str] = None
    try:
        from pathlib import Path
        tmpdir = tempfile.mkdtemp(prefix="autodoc_zip_")

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(tmpdir)

        repo_path = Path(tmpdir)

        # If no .git dir, create a synthetic git repo so autodoc can run
        if not (repo_path / ".git").exists():
            subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "autodoc@demo.local"],
                cwd=tmpdir, check=True, capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "AutoDoc Demo"],
                cwd=tmpdir, check=True, capture_output=True,
            )
            subprocess.run(["git", "add", "-A"], cwd=tmpdir, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "init"],
                cwd=tmpdir, check=True, capture_output=True,
            )

        _run_processing(
            job_id,
            repo_path,
            "HEAD~1",
            "HEAD",
            all_files=True,
            preflight_llm=not mock_generation,
            mock_generation=mock_generation,
        )
    except Exception as e:
        _set_job(job_id, status=JobStatus.FAILED, finished_at=_utc_now(), phase="failed", phase_message="Job failed", error=str(e))
        _emit_event(job_id, JobEvent(event="job_failed", job_id=job_id, phase="failed", phase_message="Job failed", error=str(e)))
        _schedule_queue_cleanup(job_id)
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ─── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": PROMPT_VERSION}


@app.post("/generate", dependencies=[Depends(_check_auth)])
def generate(req: GenerateRequest, background_tasks: BackgroundTasks) -> dict:
    job_id = str(uuid.uuid4())
    record = JobRecord(
        job_id=job_id,
        status=JobStatus.PENDING,
        created_at=_utc_now(),
    )
    with _jobs_lock:
        _jobs[job_id] = record
    background_tasks.add_task(run_generate_job, job_id, req)
    return {"job_id": job_id, "status": JobStatus.PENDING, "poll_url": f"/jobs/{job_id}"}


@app.get("/jobs/{job_id}", dependencies=[Depends(_check_auth)])
def get_job(job_id: str) -> JobRecord:
    with _jobs_lock:
        record = _jobs.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return record


@app.get("/jobs/{job_id}/stream")
async def stream_job_events(job_id: str) -> StreamingResponse:
    with _jobs_lock:
        if job_id not in _jobs:
            raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        loop = asyncio.get_event_loop()
        keepalive_interval = 30.0
        last_keepalive = loop.time()
        max_wait = 600.0
        start_time = loop.time()

        while loop.time() - start_time < max_wait:
            with _job_queues_lock:
                q = _job_queues.get(job_id)

            if q is None:
                # No queue — check if job finished
                with _jobs_lock:
                    record = _jobs.get(job_id)
                if record and record.status in (JobStatus.DONE, JobStatus.FAILED):
                    ev_name = "job_done" if record.status == JobStatus.DONE else "job_failed"
                    final = JobEvent(
                        event=ev_name, job_id=job_id,
                        units=[u.model_dump() for u in (record.units or [])],
                        repo_doc=record.repo_doc,
                        error=record.error,
                    )
                    yield f"data: {final.model_dump_json()}\n\n"
                    break
                # Still running without a queue — send keepalive and wait
                await asyncio.sleep(2)
                now = loop.time()
                if now - last_keepalive >= keepalive_interval:
                    yield ": keepalive\n\n"
                    last_keepalive = now
                continue

            try:
                event: JobEvent = await loop.run_in_executor(
                    None, lambda: q.get(timeout=1.0)
                )
                yield f"data: {event.model_dump_json()}\n\n"
                if event.event in ("job_done", "job_failed"):
                    break
            except _queue.Empty:
                now = loop.time()
                if now - last_keepalive >= keepalive_interval:
                    yield ": keepalive\n\n"
                    last_keepalive = now

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/jobs/{job_id}/diagnostics")
def get_job_diagnostics(job_id: str):
    """Return a Markdown diagnostics report for a job (claw-code as_markdown() pattern)."""
    from fastapi.responses import PlainTextResponse
    with _jobs_lock:
        record = _jobs.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")

    lines = [
        f"# AutoDoc Job Diagnostics: `{job_id}`",
        "",
        "## Summary",
        f"- **Status**: {record.status.value}",
        f"- **Created**: {record.created_at}",
        f"- **Finished**: {record.finished_at or 'in progress'}",
    ]
    if record.error:
        lines.append(f"- **Error**: {record.error}")

    units = record.units or []
    if units:
        lines += ["", f"## Units ({len(units)})", ""]
        lines.append("| Unit | Kind | Status | Quality | Sections |")
        lines.append("|------|------|--------|---------|----------|")
        for u in units:
            q = u.quality or {}
            score = f"{q.get('overall_score', 0):.2f}" if q else "—"
            sec = f"{int(q.get('section_completeness', 0) * 6)}/6" if q else "—"
            lines.append(f"| {u.name} | {u.kind} | {u.status} | {score} | {sec} |")

        scores = [u.quality.get("overall_score", 0) for u in units if u.quality]
        if scores:
            avg = sum(scores) / len(scores)
            best = max(units, key=lambda u: (u.quality or {}).get("overall_score", 0))
            worst = min(units, key=lambda u: (u.quality or {}).get("overall_score", 0))
            lines += [
                "",
                "## Quality Overview",
                f"- Average score: **{avg:.2f}**",
                f"- Highest: {best.name} ({(best.quality or {}).get('overall_score', 0):.2f})",
                f"- Lowest: {worst.name} ({(worst.quality or {}).get('overall_score', 0):.2f})",
            ]

        failed = [u for u in units if u.status.startswith("failed")]
        lines += ["", "## Errors"]
        if failed:
            for u in failed:
                lines.append(f"- **{u.name}**: {u.status}")
        else:
            lines.append("- None")

    return PlainTextResponse("\n".join(lines), media_type="text/markdown")


@app.get("/sessions", dependencies=[Depends(_check_auth)])
def list_sessions_endpoint(limit: int = 50):
    """List recent persisted job sessions (newest first)."""
    from autodoc.session import list_sessions
    sessions = list_sessions(limit=limit)
    return {"sessions": [s.__dict__ for s in sessions]}


@app.get("/sessions/{job_id}", dependencies=[Depends(_check_auth)])
def get_session(job_id: str):
    """Load a specific persisted session by job_id."""
    from autodoc.session import load_session
    session = load_session(job_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.__dict__


@app.post("/demo/generate")
def demo_generate(req: DemoGenerateRequest, background_tasks: BackgroundTasks) -> dict:
    job_id = str(uuid.uuid4())
    record = JobRecord(job_id=job_id, status=JobStatus.PENDING, created_at=_utc_now())
    q: _queue.Queue = _queue.Queue()
    with _jobs_lock:
        _jobs[job_id] = record
    with _job_queues_lock:
        _job_queues[job_id] = q
    background_tasks.add_task(run_demo_generate_job, job_id, req)
    return {
        "job_id": job_id,
        "status": JobStatus.PENDING,
        "poll_url": f"/jobs/{job_id}",
        "stream_url": f"/jobs/{job_id}/stream",
    }


@app.post("/demo/generate-zip")
async def demo_generate_zip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mock_generation: bool = Form(False),
) -> dict:
    job_id = str(uuid.uuid4())
    record = JobRecord(job_id=job_id, status=JobStatus.PENDING, created_at=_utc_now())
    q: _queue.Queue = _queue.Queue()
    with _jobs_lock:
        _jobs[job_id] = record
    with _job_queues_lock:
        _job_queues[job_id] = q
    zip_bytes = await file.read()
    background_tasks.add_task(run_demo_zip_job, job_id, zip_bytes, mock_generation)
    return {
        "job_id": job_id,
        "status": JobStatus.PENDING,
        "poll_url": f"/jobs/{job_id}",
        "stream_url": f"/jobs/{job_id}/stream",
    }


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    import uvicorn
    uvicorn.run("autodoc.server:app", host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
