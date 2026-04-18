import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from backend.models import (
    LocalReviewLabResponse, LocalTrackInfo, TrackAnalysis,
    LocalResolveRequest, LocalBatchResolveRequest,
    ResolveResponse, BatchResolveResponse,
)
from backend.state import create_ecl_session, get_ecl_session
from backend.utils import validate_local_path
import engine

router = APIRouter()
logger = logging.getLogger(__name__)


def _check_track_in_review(track_path: str, review_folder: str) -> None:
    """Reject track paths that resolve outside the session's review folder."""
    try:
        resolved_track  = Path(track_path).resolve()
        resolved_review = Path(review_folder).resolve()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid track path")
    if not resolved_track.is_relative_to(resolved_review):
        raise HTTPException(status_code=400, detail="Track path is outside the review folder")


@router.get("/api/local-review-lab", response_model=LocalReviewLabResponse)
def load_local_review_lab(folder_path: str = Query(...)):
    validate_local_path(folder_path)
    try:
        data = engine.load_local_edge_case_lab(folder_path)
    except HTTPException:
        raise
    except Exception:
        logger.exception("load_local_edge_case_lab failed for %r", folder_path)
        raise HTTPException(status_code=500, detail="Failed to load Review Lab")

    session_id = create_ecl_session(data)
    return LocalReviewLabResponse(
        session_id=session_id,
        tracks=[LocalTrackInfo(**t) for t in data["tracks"]],
        analyses={uri: TrackAnalysis(**a) for uri, a in data["analyses"].items()},
        review_folder=data["review_folder"],
        base_path=data["base_path"],
    )


@router.post("/api/local-review-lab/resolve", response_model=ResolveResponse)
def resolve_local_track(req: LocalResolveRequest):
    session = get_ecl_session(req.session_id)
    if session is None:
        raise HTTPException(404, "Session expired — reload the Local Review Lab")

    _check_track_in_review(req.track_uri, session["review_folder"])

    ok, dest, created_new = engine.execute_local_move(
        track_path=req.track_uri,
        target_name=req.target_folder_name,
        base_path=session["base_path"],
        existing=session["existing"],   # mutated in-place — intentional
        casing=session["casing"],
    )
    if not ok:
        raise HTTPException(500, "Move failed — check server logs")

    return ResolveResponse(
        success=True,
        dest_display_name=dest,
        created_new=created_new,
        message=f"Created '{dest}' and moved file" if created_new else f"Added to existing folder '{dest}'",
    )


@router.post("/api/local-review-lab/resolve-batch", response_model=BatchResolveResponse)
def resolve_local_batch(req: LocalBatchResolveRequest):
    session = get_ecl_session(req.session_id)
    if session is None:
        raise HTTPException(404, "Session expired — reload the Local Review Lab")

    for uri in req.track_uris:
        _check_track_in_review(uri, session["review_folder"])

    moved = 0
    failed = 0
    dest_display = req.target_folder_name
    any_created_new = False

    for track_uri in req.track_uris:
        ok, dest, created_new = engine.execute_local_move(
            track_path=track_uri,
            target_name=req.target_folder_name,
            base_path=session["base_path"],
            existing=session["existing"],   # mutated in-place — folder created once, reused
            casing=session["casing"],
        )
        if ok:
            moved += 1
            dest_display = dest
            if created_new:
                any_created_new = True
        else:
            failed += 1

    if moved == 0:
        raise HTTPException(500, "All moves failed — check server logs")

    return BatchResolveResponse(
        moved=moved,
        failed=failed,
        dest_display_name=dest_display,
        created_new=any_created_new,
    )
