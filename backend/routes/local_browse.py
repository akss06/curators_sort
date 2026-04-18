from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from backend.models import BrowseEntry, BrowseResponse
import engine

router = APIRouter()


@router.get("/api/local/browse", response_model=BrowseResponse)
def browse(path: str = Query(default=None)):
    try:
        target = path or str(Path.home())
        data = engine.browse_directory(target)
        return BrowseResponse(
            current=data["current"],
            parent=data["parent"],
            dirs=[BrowseEntry(**d) for d in data["dirs"]],
            audio_count=data["audio_count"],
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
