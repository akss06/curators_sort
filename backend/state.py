"""
state.py
--------
In-memory stores for long-running sort jobs and Edge Case Lab sessions.
Both stores are module-level dicts — acceptable for a single-user local app.
"""

import uuid
from dataclasses import dataclass, field
from queue import Queue


# ---------------------------------------------------------------------------
# Sort job store
# ---------------------------------------------------------------------------

@dataclass
class SortJob:
    job_id: str
    queue: Queue = field(default_factory=Queue)
    # Items pushed by the worker thread:
    #   {"type": "progress", "current": int, "total": int, "track": str}
    #   {"type": "complete",  "logs": list[dict]}
    #   {"type": "error",     "message": str}


_sort_jobs: dict[str, SortJob] = {}


def create_sort_job() -> SortJob:
    job = SortJob(job_id=str(uuid.uuid4()))
    _sort_jobs[job.job_id] = job
    return job


def get_sort_job(job_id: str) -> SortJob | None:
    return _sort_jobs.get(job_id)


def delete_sort_job(job_id: str) -> None:
    _sort_jobs.pop(job_id, None)


# ---------------------------------------------------------------------------
# Edge Case Lab session store
# ---------------------------------------------------------------------------

_ecl_sessions: dict[str, dict] = {}
# Stores the full load_edge_case_lab() return dict.
# The "existing" and "casing" sub-dicts are mutated in-place by
# execute_move_from_review — this is intentional and load-bearing.


def create_ecl_session(data: dict) -> str:
    sid = str(uuid.uuid4())
    _ecl_sessions[sid] = data
    return sid


def get_ecl_session(sid: str) -> dict | None:
    return _ecl_sessions.get(sid)
