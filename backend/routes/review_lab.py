import logging

import spotipy
from fastapi import APIRouter, HTTPException

from backend.models import (
    ReviewLabResponse,
    ResolveRequest,
    ResolveResponse,
    TrackInfo,
    TrackAnalysis,
)
from backend.state import create_ecl_session, get_ecl_session
import engine

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/review-lab", response_model=ReviewLabResponse)
def load_review_lab():
    """
    Fetch tracks from Review / Misc and run Groq analysis on each.
    Long-running — client should show a loading indicator.
    Returns a session_id that must be included in all resolve calls.
    """
    try:
        data = engine.load_edge_case_lab()
    except spotipy.SpotifyException as exc:
        if exc.http_status == 429:
            raise HTTPException(status_code=429, detail="Spotify API rate limit reached. Please wait a few minutes and try again.")
        logger.exception("Spotify error loading Review Lab")
        raise HTTPException(status_code=500, detail="Failed to load Review Lab")
    except Exception:
        logger.exception("Unexpected error loading Review Lab")
        raise HTTPException(status_code=500, detail="Failed to load Review Lab")

    session_id = create_ecl_session(data)

    return ReviewLabResponse(
        session_id=session_id,
        tracks=[TrackInfo(**t) for t in data["tracks"]],
        analyses={
            uri: TrackAnalysis(**analysis)
            for uri, analysis in data["analyses"].items()
        },
        review_pid=data["review_pid"],
    )


@router.post("/api/review-lab/resolve", response_model=ResolveResponse)
def resolve_track(req: ResolveRequest):
    """
    Move a track out of Review / Misc.
    Smart routing: if target_playlist_name matches an existing playlist
    (case-insensitive), routes there instead of creating a duplicate.
    The session's existing/casing dicts are mutated in-place so newly
    created playlists are visible to subsequent resolve calls.
    """
    session = get_ecl_session(req.session_id)
    if session is None:
        raise HTTPException(
            status_code=404,
            detail="Session expired — reload the Edge Case Lab",
        )

    ok, dest, created_new = engine.execute_move_from_review(
        track_uri=req.track_uri,
        target_name=req.target_playlist_name,
        review_pid=session["review_pid"],
        existing_playlists=session["existing"],  # mutated in-place — intentional
        casing_map=session["casing"],
        user_id=session["user_id"],
    )

    if not ok:
        raise HTTPException(status_code=500, detail="Move failed — check server logs")

    return ResolveResponse(
        success=True,
        dest_display_name=dest,
        created_new=created_new,
        message=(
            f"Created '{dest}' and moved track"
            if created_new
            else f"Added to existing playlist '{dest}'"
        ),
    )
