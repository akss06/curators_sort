import json
import threading

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from backend.models import LocalSortStartRequest, SortStartResponse
from backend.state import create_sort_job, get_sort_job, delete_sort_job
import engine

router = APIRouter()


@router.post("/api/local-sort/start", response_model=SortStartResponse)
def start_local_sort(req: LocalSortStartRequest):
    _ai_set       = {"Activity", "Vibe", "Genre"}
    _metadata_set = {"Artist", "Album"}
    pset = set(req.priorities)
    valid = (pset == _ai_set and len(req.priorities) == 3) or \
            (pset == _metadata_set and len(req.priorities) == 2)
    if not valid:
        raise HTTPException(
            400,
            "priorities must be exactly AI (Activity, Vibe, Genre) "
            "or exactly Metadata (Artist, Album)",
        )

    job = create_sort_job()

    def _worker():
        def _progress(current: int, total: int, track_name: str):
            job.queue.put({"type": "progress", "current": current, "total": total, "track": track_name})

        try:
            logs = engine.run_local_sorter(
                folder_path=req.folder_path,
                user_config={"hierarchy": req.priorities},
                limit=req.limit,
                allow_new_folders=req.allow_new_folders,
                progress_callback=_progress,
                dry_run=req.dry_run,
                confidence_threshold=req.confidence_threshold,
            )
            job.queue.put({"type": "complete", "logs": logs})
        except Exception as exc:
            job.queue.put({"type": "error", "message": str(exc)})

    threading.Thread(target=_worker, daemon=True).start()
    return SortStartResponse(job_id=job.job_id)


@router.get("/api/local-sort/stream/{job_id}")
def stream_local_sort(job_id: str):
    job = get_sort_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    async def _generator():
        while True:
            msg = job.queue.get()
            msg_type = msg.pop("type")
            yield {"event": msg_type, "data": json.dumps(msg)}
            if msg_type in ("complete", "error"):
                delete_sort_job(job_id)
                break

    return EventSourceResponse(_generator())
