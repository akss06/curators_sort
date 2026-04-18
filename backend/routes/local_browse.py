import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from backend.models import BrowseEntry, BrowseResponse
from backend.utils import validate_local_path
import engine

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/local/browse", response_model=BrowseResponse)
def browse(path: str = Query(default=None)):
    target = path or str(Path.home())
    validate_local_path(target)
    try:
        data = engine.browse_directory(target)
        return BrowseResponse(
            current=data["current"],
            parent=data["parent"],
            dirs=[BrowseEntry(**d) for d in data["dirs"]],
            audio_count=data["audio_count"],
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("browse_directory failed for path %r", target)
        raise HTTPException(status_code=500, detail="Failed to browse directory")
