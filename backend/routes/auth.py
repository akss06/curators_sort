from fastapi import APIRouter
from backend.models import AuthStatusResponse
import engine

router = APIRouter()


@router.get("/api/auth/status", response_model=AuthStatusResponse)
def auth_status():
    """Check whether the cached Spotify token is present and valid."""
    try:
        sp = engine.get_spotify_client()
        user = engine._retry_spotify(sp.current_user)
        return AuthStatusResponse(
            authenticated=True,
            user_id=user["id"],
            display_name=user.get("display_name"),
        )
    except Exception:
        return AuthStatusResponse(authenticated=False)
