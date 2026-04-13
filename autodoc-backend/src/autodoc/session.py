from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# Server-side sessions directory. Defaults to /tmp/autodoc_sessions so it
# survives repo tmpdir cleanup. Override with AUTODOC_SESSIONS_DIR env var.
_SESSIONS_DIR = Path(os.environ.get("AUTODOC_SESSIONS_DIR", "/tmp/autodoc_sessions"))
_sessions_lock = threading.Lock()


@dataclass
class PersistedSession:
    job_id: str
    repo_name: str
    base_ref: str
    head_ref: str
    status: str                        # "running" | "completed" | "failed"
    created_at: str
    finished_at: Optional[str]
    total_units: int
    units_completed: list[str]         # slugs processed successfully
    units_failed: list[str]            # slugs that errored
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    error: Optional[str] = None
    fast_model: str = ""
    smart_model: str = ""


def _session_path(job_id: str) -> Path:
    return _SESSIONS_DIR / f"{job_id}.json"


def save_session(session: PersistedSession) -> None:
    """Write session to disk. Thread-safe."""
    with _sessions_lock:
        _SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        p = _session_path(session.job_id)
        p.write_text(json.dumps(asdict(session), indent=2), encoding="utf-8")


def load_session(job_id: str) -> Optional[PersistedSession]:
    """Load a single session by job_id. Returns None if not found."""
    p = _session_path(job_id)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return PersistedSession(**data)
    except Exception:
        return None


def list_sessions(limit: int = 50) -> list[PersistedSession]:
    """List recent sessions, newest first."""
    if not _SESSIONS_DIR.exists():
        return []
    sessions: list[PersistedSession] = []
    paths = sorted(_SESSIONS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in paths[:limit]:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            sessions.append(PersistedSession(**data))
        except Exception:
            continue
    return sessions
