"""
models.py
---------
Pydantic request and response schemas for the Curator's Sorter API.
"""

from typing import Literal
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class SortStartRequest(BaseModel):
    priorities: list[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="1–5 unique values from ['Activity', 'Vibe', 'Genre', 'Artist', 'Album'] in priority order.",
    )
    limit: int = Field(50, ge=10, le=200)
    remove_from_liked: bool = True
    allow_new_playlists: bool = True
    dry_run: bool = False
    confidence_threshold: int = Field(85, ge=50, le=99)


class ResolveRequest(BaseModel):
    track_uri: str
    target_playlist_name: str = Field(..., min_length=1, max_length=255, pattern=r'^[^\n\r\x00]+$')
    session_id: str = Field(..., description="session_id returned by GET /api/review-lab")


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class AuthStatusResponse(BaseModel):
    authenticated: bool
    user_id: str | None = None
    display_name: str | None = None


class PlaylistItem(BaseModel):
    id: str
    name: str
    track_count: int = 0
    external_url: str = ""


class PlaylistsResponse(BaseModel):
    playlists: list[PlaylistItem]


class RunStats(BaseModel):
    total: int
    sorted: int
    duplicates: int
    review: int
    new_playlists: int


class LogEntry(BaseModel):
    track: str
    artist: str
    genre: str
    vibe: str
    confidence: int
    reasoning: str
    destination: str
    resolution: Literal["EXISTING", "NEW", "REVIEW", "ERROR"]
    status: str
    image_url: str | None = None


class RunEntry(BaseModel):
    id: str
    timestamp: str
    priorities: list[str]
    limit: int
    remove_from_liked: bool
    allow_new_playlists: bool
    dry_run: bool
    confidence_threshold: int
    stats: RunStats
    logs: list[LogEntry]


class RunsResponse(BaseModel):
    runs: list[RunEntry]


class SortStartResponse(BaseModel):
    job_id: str


class TrackInfo(BaseModel):
    id: str
    name: str
    artist: str
    album: str
    uri: str
    image_url: str | None = None


class TrackAnalysis(BaseModel):
    reasoning: str
    suggested_existing: str   # exact playlist display name, or "NONE"
    suggested_new: str


class ReviewLabResponse(BaseModel):
    session_id: str
    tracks: list[TrackInfo]
    analyses: dict[str, TrackAnalysis]   # keyed by track URI
    review_pid: str


class ResolveResponse(BaseModel):
    success: bool
    dest_display_name: str
    created_new: bool
    message: str


# ---------------------------------------------------------------------------
# Local Files
# ---------------------------------------------------------------------------

class LocalSortStartRequest(BaseModel):
    folder_path: str
    priorities: list[str] = Field(
        ..., min_length=1, max_length=5,
        description="1–5 unique values from ['Activity', 'Vibe', 'Genre', 'Artist', 'Album'] in priority order.",
    )
    limit: int = Field(200, ge=10, le=500)
    allow_new_folders: bool = True
    dry_run: bool = False
    confidence_threshold: int = Field(85, ge=50, le=99)


class LocalTrackInfo(BaseModel):
    id: str
    name: str
    artist: str
    album: str
    uri: str        # absolute file path — used as identifier
    format: str     # mp3 / flac / m4a / etc.
    duration_ms: int | None = None


class LocalReviewLabResponse(BaseModel):
    session_id: str
    tracks: list[LocalTrackInfo]
    analyses: dict[str, TrackAnalysis]  # keyed by uri (file path)
    review_folder: str
    base_path: str


class LocalResolveRequest(BaseModel):
    track_uri: str                       # absolute file path
    target_folder_name: str = Field(..., min_length=1, max_length=255)
    session_id: str


class LocalBatchResolveRequest(BaseModel):
    track_uris: list[str] = Field(..., min_length=1)
    target_folder_name: str = Field(..., min_length=1, max_length=255)
    session_id: str


class BatchResolveResponse(BaseModel):
    moved: int
    failed: int
    dest_display_name: str
    created_new: bool


class BrowseEntry(BaseModel):
    name: str
    path: str
    audio_count: int


class BrowseResponse(BaseModel):
    current: str
    parent: str | None
    dirs: list[BrowseEntry]
    audio_count: int
