from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from autodoc.prompts import PROMPT_VERSION

app = FastAPI(title="AutoDoc API", version=PROMPT_VERSION)

_jobs: dict[str, "JobRecord"] = {}
_jobs_lock = threading.Lock()

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
    repo_path: str
    base: str = "HEAD~1"
    head: str = "HEAD"
    model: Optional[str] = None
    all_files: bool = False
    config_path: Optional[str] = None


class UnitResult(BaseModel):
    slug: str
    name: str
    kind: str
    markdown: str
    status: str


class JobRecord(BaseModel):
    job_id: str
    status: JobStatus
    created_at: str
    finished_at: Optional[str] = None
    units: Optional[list[UnitResult]] = None
    repo_doc: Optional[str] = None
    error: Optional[str] = None


# ─── Background job ───────────────────────────────────────────────────────────

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_job(job_id: str, **kwargs) -> None:
    with _jobs_lock:
        record = _jobs[job_id]
        updated = record.model_copy(update=kwargs)
        _jobs[job_id] = updated


def run_generate_job(job_id: str, req: GenerateRequest) -> None:
    _set_job(job_id, status=JobStatus.RUNNING)

    try:
        from pathlib import Path
        from autodoc.cache import AUTODOC_DIR, cache_exists, compute_cache_key, get_cache_paths, save_cache_entry, prune_cache, append_changelog_entry
        from autodoc.config import load_config
        from autodoc.context import (
            read_repo_readme, group_files_into_units, merge_small_groups,
            merge_by_import_coupling, make_units_from_groups, build_unit_context_bundle,
            apply_unit_overrides,
        )
        from autodoc.repo_index import load_index, save_index, build_repo_index, diff_indices, impacted_units, utc_now_iso, build_import_graph
        from autodoc.filters import get_all_relevant_files_git, is_probably_text_file
        from autodoc.git_utils import ensure_git_repo, get_changed_files
        from autodoc.llm import generate_documentation, generate_repo_documentation
        from autodoc.prompts import build_repo_prompt, build_unit_prompt, build_unit_patch_prompt
        from autodoc.router import route_model

        repo_path = Path(req.repo_path).resolve()

        cfg_file = Path(req.config_path) if req.config_path else None
        cfg = load_config(repo_path, cfg_file)
        if req.model:
            cfg.fast_model = req.model
            cfg.smart_model = req.model

        ensure_git_repo(repo_path)

        all_candidates = get_all_relevant_files_git(repo_path)
        all_paths = [c.path for c in all_candidates]

        raw_groups = group_files_into_units(all_paths)
        raw_groups = apply_unit_overrides(raw_groups, cfg.unit_overrides, all_paths)

        try:
            _raw_imports, _resolved = build_import_graph(repo_path, all_paths)
            deps: dict[str, set[str]] = {k: set(v) for k, v in _resolved.items()}
        except Exception:
            deps = {}

        groups = merge_by_import_coupling(raw_groups, deps)
        groups = merge_small_groups(groups, min_files=cfg.min_files_per_unit)
        all_units = make_units_from_groups(groups)

        if not all_units:
            _set_job(job_id, status=JobStatus.DONE, finished_at=_utc_now(), units=[], repo_doc=None)
            return

        changed_files_set: set[str] = set()
        if req.all_files:
            changed_files_set = set(all_paths)
        else:
            changed = get_changed_files(repo_path, req.base, req.head)
            changed_files_set = {
                c.path for c in changed
                if c.status != "D" and is_probably_text_file(c.path)
            }

        old_idx = load_index(repo_path)
        new_idx = build_repo_index(repo_path, all_units, all_paths)
        struct = diff_indices(old_idx, new_idx)

        if req.all_files:
            units_to_run = all_units
        else:
            impacted_roots = set()
            impacted_roots.update(struct.get("added_units", []))
            impacted_roots.update(struct.get("changed_units", []))
            impacted_roots.update(impacted_units(new_idx, changed_files_set, depth=2))
            units_to_run = [u for u in all_units if u.root in impacted_roots]

        units_dir = repo_path / AUTODOC_DIR / "units"
        units_dir.mkdir(parents=True, exist_ok=True)

        unit_results: list[UnitResult] = []

        for unit in units_to_run:
            stable_path = units_dir / f"{unit.slug}.md"

            try:
                bundle = build_unit_context_bundle(
                    repo_path, req.base, req.head, unit,
                    include_diff=not req.all_files,
                    changed_files=changed_files_set,
                    max_file_chars=cfg.max_file_chars,
                    max_files_fulltext=cfg.max_files_fulltext,
                    token_budget=cfg.token_budget,
                    all_units=all_units,
                    deps=deps,
                )
                decision = route_model(unit, changed_files_set, bundle.diffs, bundle.existing_unit_doc, cfg)

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

                if cache_exists(repo_path, cache_key):
                    md_path, _ = get_cache_paths(repo_path, cache_key)
                    markdown = md_path.read_text(encoding="utf-8")
                    status_label = "cached"
                else:
                    markdown, usage = generate_documentation(prompt_text, unit.slug, model=decision.model)
                    md_path, _ = save_cache_entry(
                        repo=repo_path, cache_key=cache_key, markdown=markdown,
                        source_file=unit.root, model_name=decision.model,
                        prompt_version=PROMPT_VERSION, base_ref=req.base, head_ref=req.head,
                        mode=decision.mode, routing_reason=decision.reason,
                        prompt_tokens=usage.prompt_tokens,
                        completion_tokens=usage.completion_tokens,
                        estimated_cost_usd=usage.estimated_cost_usd,
                    )
                    append_changelog_entry(stable_path, decision.mode, decision.model, req.base, req.head)
                    status_label = decision.mode

                try:
                    stable_path.write_text(markdown, encoding="utf-8")
                except Exception:
                    pass

                unit_results.append(UnitResult(
                    slug=unit.slug,
                    name=unit.name,
                    kind=unit.kind,
                    markdown=markdown,
                    status=status_label,
                ))

            except Exception as e:
                unit_results.append(UnitResult(
                    slug=unit.slug,
                    name=unit.name,
                    kind=unit.kind,
                    markdown="",
                    status=f"failed: {e}",
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
            repo_prompt = build_repo_prompt(
                repo_name=repo_path.name,
                readme_content=repo_readme,
                file_docs=unit_docs,
            )
            repo_markdown = generate_repo_documentation(repo_prompt, model=cfg.smart_model)
            repo_doc_path = repo_path / AUTODOC_DIR / "REPOSITORY.md"
            repo_doc_path.write_text(repo_markdown, encoding="utf-8")

        new_idx.updated_at_utc = utc_now_iso()
        save_index(repo_path, new_idx)

        _set_job(job_id, status=JobStatus.DONE, finished_at=_utc_now(), units=unit_results, repo_doc=repo_markdown)

    except Exception as e:
        _set_job(job_id, status=JobStatus.FAILED, finished_at=_utc_now(), error=str(e))


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


# ─── Entry point ──────────────────────────────────────────────────────────────

def main() -> None:
    import uvicorn
    uvicorn.run("autodoc.server:app", host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
