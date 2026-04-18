import spotipy
from fastapi import APIRouter, HTTPException
from backend.models import PlaylistsResponse, PlaylistItem
import engine

router = APIRouter()


@router.get("/api/playlists", response_model=PlaylistsResponse)
def get_playlists():
    """Return all playlists owned by the authenticated user, with track counts."""
    try:
        sp = engine.get_spotify_client()
        user_id = engine._retry_spotify(sp.current_user)["id"]

        playlists: list[PlaylistItem] = []
        results = engine._retry_spotify(sp.current_user_playlists, limit=50)
        while results:
            for item in results["items"]:
                if item is None:
                    continue
                if item.get("owner", {}).get("id") != user_id:
                    continue
                playlists.append(PlaylistItem(
                    id=item["id"],
                    name=item["name"],
                    track_count=(item.get("items") or item.get("tracks") or {}).get("total", 0),
                    external_url=item.get("external_urls", {}).get("spotify", ""),
                ))
            if not results["next"]:
                break
            results = engine._retry_spotify(sp.next, results)

        playlists.sort(key=lambda p: p.name.lower())
        return PlaylistsResponse(playlists=playlists)
    except Exception as exc:
        if isinstance(exc, spotipy.SpotifyException) and exc.http_status == 429:
            raise HTTPException(status_code=429, detail="Spotify API rate limit reached. Please wait a few minutes and try again.")
        raise HTTPException(status_code=500, detail=str(exc))
