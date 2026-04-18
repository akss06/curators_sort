import asyncio
import json
import logging
import os
import queue
import threading
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from backend.models import SortStartRequest, SortStartResponse
from backend.state import create_sort_job, get_sort_job, delete_sort_job
import engine

router = APIRouter()
logger = logging.getLogger(__name__)

RUNS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "runs.jsonl")


def _save_run(req: SortStartRequest, logs: list[dict]) -> None:
    sorted_count = sum(
        1 for l in logs
        if l.get("resolution") in ("EXISTING", "NEW")
    )
    dup_count    = sum(1 for l in logs if l.get("status", "").startswith("Skipped"))
    review_count = sum(1 for l in logs if l.get("resolution") == "REVIEW")
    new_count    = sum(1 for l in logs if l.get("resolution") == "NEW")

    entry = {
        "id":                 str(uuid.uuid4()),
        "timestamp":          datetime.now(timezone.utc).isoformat(),
        "priorities":         req.priorities,
        "limit":              req.limit,
        "remove_from_liked":  req.remove_from_liked,
        "allow_new_playlists": req.allow_new_playlists,
        "dry_run":            req.dry_run,
        "confidence_threshold": req.confidence_threshold,
        "stats": {
            "total":        len(logs),
            "sorted":       sorted_count,
            "duplicates":   dup_count,
            "review":       review_count,
            "new_playlists": new_count,
        },
        "logs": logs,
    }
    try:
        with open(RUNS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
    except Exception as exc:
        logger.warning("Failed to save run history: %s", exc)


@router.post("/api/sort/start", response_model=SortStartResponse)
def start_sort(req: SortStartRequest):
    allowed = {"Activity", "Vibe", "Genre"}
    if set(req.priorities) != allowed or len(req.priorities) != 3:
        raise HTTPException(
            status_code=400,
            detail="priorities must be exactly one each of Activity, Vibe, Genre",
        )

    job = create_sort_job()

    def _worker() -> None:
        def _progress(current: int, total: int, track_name: str) -> None:
            job.queue.put({
                "type":    "progress",
                "current": current,
                "total":   total,
                "track":   track_name,
            })

        try:
            logs = engine.run_sorter(
                user_config={"hierarchy": req.priorities},
                limit=req.limit,
                remove_from_liked=req.remove_from_liked,
                allow_new_playlists=req.allow_new_playlists,
                progress_callback=_progress,
                dry_run=req.dry_run,
                confidence_threshold=req.confidence_threshold,
            )
            _save_run(req, logs)
            job.queue.put({"type": "complete", "logs": logs})
        except Exception as exc:
            job.queue.put({"type": "error", "message": str(exc)})

    threading.Thread(target=_worker, daemon=True).start()
    return SortStartResponse(job_id=job.job_id)


@router.get("/api/sort/stream/{job_id}")
def stream_sort(job_id: str):
    job = get_sort_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def _generator():
        """Non-blocking async generator that polls the queue."""
        while True:
            # Use non-blocking get_nowait() in a loop with small sleeps
            # to avoid blocking the event loop
            msg = None
            while msg is None:
                try:
                    msg = job.queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.1)

            msg_type = msg.pop("type")
            yield {"event": msg_type, "data": json.dumps(msg)}
            if msg_type in ("complete", "error"):
                delete_sort_job(job_id)
                break

    return EventSourceResponse(_generator())
