import json
import os

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

RUNS_FILE = os.path.join(os.path.dirname(__file__), "..", "..", "runs.jsonl")


@router.get("/api/runs")
def get_runs(limit: int = Query(20, ge=1, le=100)):
    """Return the last `limit` sort runs, newest first."""
    try:
        with open(RUNS_FILE, "r", encoding="utf-8") as f:
            lines = [l for l in f.readlines() if l.strip()]
        runs = [json.loads(l) for l in lines[-limit:]]
        runs.reverse()
        return {"runs": runs}
    except FileNotFoundError:
        return {"runs": []}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
