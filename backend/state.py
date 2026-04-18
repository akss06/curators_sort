"""
state.py
--------
In-memory stores for long-running sort jobs and Edge Case Lab sessions.
Both stores are module-level dicts — acceptable for a single-user local app.
"""

import time
import threading
import uuid
from dataclasses import dataclass, field
from queue import Queue


_SESSION_TTL = 2 * 3600   # sessions expire after 2 hours
_JOB_TTL     = 3600       # orphaned jobs (client disconnected) expire after 1 hour

_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Sort job store
# ---------------------------------------------------------------------------

@dataclass
class SortJob:
    job_id: str
    created_at: float = field(default_factory=time.time)
    queue: Queue = field(default_factory=Queue)
    # Items pushed by the worker thread:
    #   {"type": "progress", "current": int, "total": int, "track": str}
    #   {"type": "complete",  "logs": list[dict]}
    #   {"type": "error",     "message": str}


_sort_jobs: dict[str, SortJob] = {}


def create_sort_job() -> SortJob:
    job = SortJob(job_id=str(uuid.uuid4()))
    with _lock:
        _sort_jobs[job.job_id] = job
    return job


def get_sort_job(job_id: str) -> SortJob | None:
    return _sort_jobs.get(job_id)


def delete_sort_job(job_id: str) -> None:
    with _lock:
        _sort_jobs.pop(job_id, None)


# ---------------------------------------------------------------------------
# Edge Case Lab session store
# ---------------------------------------------------------------------------

_ecl_sessions: dict[str, dict] = {}
# Stores the full load_edge_case_lab() return dict plus "_created_at".
# The "existing" and "casing" sub-dicts are mutated in-place by
# execute_move_from_review — this is intentional and load-bearing.


def create_ecl_session(data: dict) -> str:
    sid = str(uuid.uuid4())
    data["_created_at"] = time.time()
    with _lock:
        _ecl_sessions[sid] = data
    return sid


def get_ecl_session(sid: str) -> dict | None:
    return _ecl_sessions.get(sid)


# ---------------------------------------------------------------------------
# Background cleanup — evicts stale sessions and orphaned jobs
# ---------------------------------------------------------------------------

def _cleanup_loop() -> None:
    while True:
        time.sleep(1800)  # run every 30 minutes
        now = time.time()
        with _lock:
            stale_sessions = [
                sid for sid, d in _ecl_sessions.items()
                if now - d.get("_created_at", now) > _SESSION_TTL
            ]
            for sid in stale_sessions:
                del _ecl_sessions[sid]

            stale_jobs = [
                jid for jid, j in _sort_jobs.items()
                if now - j.created_at > _JOB_TTL
            ]
            for jid in stale_jobs:
                del _sort_jobs[jid]


threading.Thread(target=_cleanup_loop, daemon=True, name="state-cleanup").start()
