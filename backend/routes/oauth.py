import os

import spotipy
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from spotipy.cache_handler import CacheFileHandler
from spotipy.oauth2 import SpotifyOAuth

router = APIRouter()

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI", "http://localhost:8000/api/oauth/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")

_SCOPE = (
    "playlist-read-private playlist-modify-private "
    "playlist-modify-public user-library-read user-library-modify"
)


def _spotify_auth() -> SpotifyOAuth:
    return SpotifyOAuth(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        redirect_uri=SPOTIFY_REDIRECT_URI,
        scope=_SCOPE,
        cache_handler=CacheFileHandler(".cache"),
    )


@router.get("/api/oauth/login")
def oauth_login():
    """Initiate Spotify OAuth flow."""
    auth_url = _spotify_auth().get_authorize_url()
    return {"auth_url": auth_url}


@router.get("/api/oauth/callback")
def oauth_callback(code: str = None, error: str = None):
    """Handle Spotify OAuth redirect."""
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")
    try:
        _spotify_auth().get_access_token(code)
        return RedirectResponse(url=FRONTEND_URL)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
