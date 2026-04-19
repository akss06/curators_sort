"""
engine.py
---------
All backend logic for The Exhausted Curator's Sorter.
MUST NOT import streamlit. Zero UI calls.
"""

import hashlib
import itertools
import json
import logging
import os
import re
import shutil
import time
from collections import defaultdict
from pathlib import Path

import mutagen
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import CacheFileHandler
from groq import Groq, APIError, APIConnectionError, RateLimitError
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------
REVIEW_PLAYLIST_NAME: str = "Review / Misc"
CONFIDENCE_THRESHOLD: int = 85
GROQ_MODEL: str = "llama-3.3-70b-versatile"     # primary: best quality, 100k TPD
GROQ_MODEL_FALLBACK: str = "llama-3.1-8b-instant"  # auto-fallback when TPD exhausted (500k TPD)
BATCH_SIZE: int = 10  # tracks per Groq API call — reduces calls from N to ceil(N/10)

_FALLBACK: dict = {
    "primary_genre": "Unknown",
    "vibe_category": REVIEW_PLAYLIST_NAME,
    "confidence_score": 0,
    "action_recommendation": "REVIEW",
    "reasoning": "Classification failed — fallback applied.",
}

# Maps each priority keyword to the reasoning style injected into the prompt.
# The active persona is chosen by whichever option the user puts at Priority 1.
_PERSONA: dict[str, str] = {
    "Genre": (
        "technical and musicological — analyse instrumentation, sub-genre, "
        "harmonic structure, and production technique"
    ),
    "Vibe": (
        "cultural and aesthetic — analyse mood, emotional resonance, "
        "atmosphere, and listener context"
    ),
    "Activity": (
        "practical and utility-driven — analyse energy level, tempo, BPM "
        "range, and use-case fit (e.g. focus, workout, commute)"
    ),
}

# Hard constraint injected into the prompt immediately after the hierarchy block.
# Forces vibe_category to match the Priority 1 category type, not default to genre names.
_VIBE_CONSTRAINT: dict[str, str] = {
    "Activity": (
        "P1=Activity: vibe_category MUST be a use-case/setting (Gym, Focus, Commute, Party, Sleep). "
        "FORBIDDEN: genre names (Rap, Pop, Jazz) as vibe_category."
    ),
    "Vibe": (
        "P1=Vibe: vibe_category MUST be a mood/aesthetic (Melancholy, Euphoric, Chill, Hype, Romantic). "
        "FORBIDDEN: genre or activity labels as vibe_category."
    ),
    "Genre": (
        "P1=Genre: vibe_category MUST be a specific genre/sub-genre (Hip-Hop/Rap, Indie Rock, City Pop, Dark Techno). "
        "Be precise — avoid broad labels when a tighter sub-genre fits."
    ),
}

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# INTERNAL HELPER — 429 retry wrapper
# ---------------------------------------------------------------------------
def _retry_spotify(fn, *args, max_attempts: int = 3, **kwargs):
    """Execute a Spotify API call with 429 rate-limit retry logic.

    Args:
        fn: Callable Spotipy method to invoke.
        *args: Positional arguments forwarded to fn.
        max_attempts: Maximum number of attempts before giving up.
        **kwargs: Keyword arguments forwarded to fn.

    Returns:
        Return value of fn.

    Raises:
        spotipy.SpotifyException: On any non-429 Spotify error.
        RuntimeError: If all retry attempts are exhausted on a 429.
    """
    for attempt in range(max_attempts):
        try:
            return fn(*args, **kwargs)
        except spotipy.SpotifyException as exc:
            if exc.http_status == 429:
                # Empty headers means Spotipy's own urllib3 retries were
                # exhausted (MaxRetryError path) — fail immediately.
                if not exc.headers:
                    raise RuntimeError(
                        "Spotify has rate-limited this app — this can last several hours. "
                        "Try again later, or use Dry Run mode to preview classifications without hitting Spotify."
                    ) from exc
                wait = int(exc.headers.get("Retry-After", 5))
                # If Spotify asks us to wait more than 60s, the daily quota
                # is exhausted — fail fast instead of sleeping for hours.
                if wait > 60:
                    raise RuntimeError(
                        f"Spotify quota exhausted (retry in ~{wait // 60} min). "
                        "Use Dry Run mode to preview classifications in the meantime."
                    ) from exc
                wait = min(wait, 30)
                logger.warning(
                    "Rate limited — waiting %ds (attempt %d/%d).",
                    wait, attempt + 1, max_attempts,
                )
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Spotify call failed after {max_attempts} attempts")


class _TpdExhausted(Exception):
    """Raised by _retry_groq when the primary model's daily token quota is hit."""


_primary_model_exhausted: bool = False  # set True once 70b TPD is hit; skips primary for session
_METADATA_PRIORITIES: frozenset[str] = frozenset({"Artist", "Album"})


# ---------------------------------------------------------------------------
# INTERNAL HELPER — 429 retry wrapper for Groq
# ---------------------------------------------------------------------------
def _parse_groq_retry_after(exc: RateLimitError) -> float:
    """Extract the suggested wait time in seconds from a Groq RateLimitError."""
    msg = str(exc)
    m = re.search(r"try again in\s+(?:(\d+)m)?([\d.]+)s", msg)
    if m:
        return int(m.group(1) or 0) * 60 + float(m.group(2) or 0)
    return 30.0


def _retry_groq(fn, *args, max_attempts: int = 3, **kwargs):
    """Execute a Groq API call with rate-limit retry logic.

    Parses the actual Retry-After from the error message. Fails immediately
    when the wait exceeds 5 minutes (daily quota exhaustion) so the caller
    surfaces a clear error rather than hanging.

    Args:
        fn: Callable Groq method to invoke.
        *args: Positional arguments forwarded to fn.
        max_attempts: Maximum number of attempts before re-raising.
        **kwargs: Keyword arguments forwarded to fn.

    Returns:
        Return value of fn.

    Raises:
        RateLimitError: If all retries are exhausted or daily quota is hit.
        APIError / APIConnectionError: On non-rate-limit Groq errors.
    """
    for attempt in range(max_attempts):
        try:
            return fn(*args, **kwargs)
        except RateLimitError as exc:
            wait = _parse_groq_retry_after(exc)
            # Daily quota (TPD) exhaustion — wait would be many minutes.
            # Fail immediately so the sort surfaces an error card rather than
            # silently spinning through three 30s sleeps.
            if wait > 300:
                logger.warning(
                    "Groq TPD quota exhausted on %s — switching to fallback model.",
                    kwargs.get("model", GROQ_MODEL),
                )
                raise _TpdExhausted(exc) from exc
            if attempt < max_attempts - 1:
                actual_wait = min(wait, 60)
                logger.warning(
                    "Groq rate limited — waiting %.0fs (attempt %d/%d).",
                    actual_wait, attempt + 1, max_attempts,
                )
                time.sleep(actual_wait)
            else:
                raise


# ---------------------------------------------------------------------------
# INTERNAL HELPER — Groq call with automatic model fallback
# ---------------------------------------------------------------------------
def _groq_call(groq_client: Groq, **kwargs):
    """Call Groq, using the fallback model immediately if primary is TPD-exhausted."""
    global _primary_model_exhausted
    model = GROQ_MODEL_FALLBACK if _primary_model_exhausted else GROQ_MODEL
    try:
        return _retry_groq(groq_client.chat.completions.create, model=model, **kwargs)
    except _TpdExhausted:
        if not _primary_model_exhausted:
            _primary_model_exhausted = True
            logger.warning(
                "Primary model TPD exhausted — using %s for all remaining calls this session.",
                GROQ_MODEL_FALLBACK,
            )
        return _retry_groq(groq_client.chat.completions.create, model=GROQ_MODEL_FALLBACK, **kwargs)


# ---------------------------------------------------------------------------
# INTERNAL HELPER — fetch sample tracks for sonic profiling
# ---------------------------------------------------------------------------
def _fetch_playlist_samples(
    sp: spotipy.Spotify,
    playlist_id: str,
    n: int = 2,
) -> list[dict]:
    """Fetch up to n tracks from a playlist to build its sonic profile.

    Args:
        sp: Authenticated Spotipy client.
        playlist_id: Spotify playlist ID to sample.
        n: Maximum number of tracks to return (default 5).

    Returns:
        List of {name, artist} dicts. Empty list on any error or empty playlist.
    """
    try:
        result = _retry_spotify(
            sp.playlist_items,
            playlist_id,
            limit=n,
            fields="items(track(name,artists(name)))",
            additional_types=["track"],
        )
        if not result:
            return []
        samples: list[dict] = []
        for item in result.get("items", []):
            t = item.get("track")
            if t and t.get("name") and t.get("artists"):
                samples.append({
                    "name":   t["name"],
                    "artist": t["artists"][0]["name"],
                })
            if len(samples) >= n:
                break
        return samples
    except Exception as exc:
        logger.warning("Could not sample playlist %s: %s", playlist_id, exc)
        return []


# ---------------------------------------------------------------------------
# INTERNAL HELPER — format a sonic bio line for the system prompt
# ---------------------------------------------------------------------------
def _build_playlist_bio(display_name: str, samples: list[dict]) -> str:
    """Format a one-line sonic bio string for a playlist.

    Args:
        display_name: Original display name of the playlist.
        samples: List of {name, artist} dicts from _fetch_playlist_samples.

    Returns:
        A single-line description of the playlist's sonic character.
    """
    if not samples:
        return f"{display_name}: (empty)"
    artists = list(dict.fromkeys(s["artist"] for s in samples))
    tracks_str = "; ".join(s["name"] for s in samples)
    return f"{display_name}: {', '.join(artists)} [{tracks_str}]"


# ---------------------------------------------------------------------------
# 3.1
# ---------------------------------------------------------------------------
def get_spotify_client() -> spotipy.Spotify:
    """Build and return an authenticated Spotipy client.

    Args:
        None

    Returns:
        spotipy.Spotify: Authenticated client backed by a cached OAuth token.

    Raises:
        RuntimeError: If Spotify OAuth fails for any reason.
    """
    scope = (
        "playlist-read-private playlist-modify-private "
        "playlist-modify-public user-library-read user-library-modify"
    )
    try:
        auth = SpotifyOAuth(
            client_id=os.getenv("SPOTIFY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
            redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback"),
            scope=scope,
            cache_handler=CacheFileHandler(cache_path=".cache"),
            open_browser=False,
        )
        # retries=0 disables Spotipy's built-in sleep-and-retry so our own
        # _retry_spotify wrapper controls all backoff logic.
        return spotipy.Spotify(auth_manager=auth, retries=0)
    except spotipy.SpotifyOauthError as exc:
        raise RuntimeError(f"Spotify auth failed: {exc}") from exc


# ---------------------------------------------------------------------------
# 3.2
# ---------------------------------------------------------------------------
def get_groq_client() -> Groq:
    """Build and return an authenticated Groq client.

    Args:
        None

    Returns:
        groq.Groq: Authenticated Groq API client.

    Raises:
        RuntimeError: If GROQ_API_KEY is absent from the environment.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY missing")
    return Groq(api_key=api_key)


# ---------------------------------------------------------------------------
# 3.3  RULE #1 — STATE CAPTURE
# ---------------------------------------------------------------------------
def fetch_existing_playlists(
    sp: spotipy.Spotify,
    user_id: str | None = None,
) -> tuple[dict, dict, dict]:
    """Fetch the user's own playlists and return three case-insensitive lookup dicts.

    Filters to playlists owned by user_id when provided, skipping followed or
    collaborative lists to keep the Sonic Profiles block concise and token-efficient.
    Also fetches up to 5 sample tracks per playlist for sonic profiling so
    the Groq prompt can distinguish playlists by content, not just name.

    RULE #1: This MUST be called before any classify_track() invocation.

    Args:
        sp: Authenticated Spotipy client.
        user_id: Spotify user ID. When supplied, only playlists whose owner
            matches are included. Pass None to include all playlists.

    Returns:
        Tuple of:
          existing_playlists — {name_lowercase: playlist_id}
          casing_map         — {name_lowercase: original_display_name}
          profiles           — {name_lowercase: list[{name, artist}]}

    Raises:
        spotipy.SpotifyException: On Spotify API failure.
    """
    existing: dict[str, str] = {}
    casing: dict[str, str] = {}
    profiles: dict[str, list[dict]] = {}

    def _ingest(item: dict) -> None:
        if user_id and item.get("owner", {}).get("id") != user_id:
            return
        key = item["name"].lower()
        existing[key] = item["id"]
        casing[key] = item["name"]
        profiles[key] = _fetch_playlist_samples(sp, item["id"])

    results = _retry_spotify(sp.current_user_playlists, limit=50)
    for item in results["items"]:
        if item is None:
            continue
        _ingest(item)

    while results["next"]:
        results = _retry_spotify(sp.next, results)
        for item in results["items"]:
            if item is None:
                continue
            _ingest(item)

    logger.info(
        "Loaded %d owned playlists with sonic profiles.", len(existing)
    )
    return existing, casing, profiles


# ---------------------------------------------------------------------------
# 3.4
# ---------------------------------------------------------------------------
def fetch_liked_tracks(sp: spotipy.Spotify, limit: int) -> list[dict]:
    """Fetch the user's Liked Songs, paginated up to the given limit.

    Args:
        sp: Authenticated Spotipy client.
        limit: Maximum number of tracks to return.

    Returns:
        List of dicts, each with keys: id, name, artist, album, uri.

    Raises:
        spotipy.SpotifyException: On non-rate-limit Spotify errors.
    """
    tracks: list[dict] = []
    offset = 0

    # Only request the fields we actually use — smaller payload, faster parsing.
    _fields = "items(track(id,name,artists(name),album(name,images(url)),uri)),next"

    while offset < limit:
        batch = min(50, limit - offset)
        page = _retry_spotify(
            sp._get, "me/tracks", limit=batch, offset=offset, fields=_fields
        )
        for item in page.get("items", []):
            t = item.get("track")
            if t:
                images = t.get("album", {}).get("images", [])
                tracks.append({
                    "id":        t["id"],
                    "name":      t["name"],
                    "artist":    t["artists"][0]["name"] if t.get("artists") else "Unknown",
                    "album":     t["album"]["name"],
                    "uri":       t["uri"],
                    "image_url": images[-1]["url"] if images else None,
                })
        if not page["next"]:
            break
        offset += batch

    logger.info("Fetched %d liked tracks.", len(tracks))
    return tracks


# ---------------------------------------------------------------------------
# 3.5  HOLY GRAIL — DYNAMIC PRIORITY INJECTION
# ---------------------------------------------------------------------------
def build_system_prompt(
    user_config: dict,
    casing_map: dict,
    profiles: dict,
    allow_new_playlists: bool = True,
    confidence_threshold: int = CONFIDENCE_THRESHOLD,
) -> str:
    """Build the Groq system prompt with dynamic priority, sonic profiles, and persona.

    Each existing playlist is described by its sample tracks so the model can
    judge genre/cultural fit rather than relying on name similarity alone.
    The hierarchy order is taken verbatim from user_config — never reordered.
    The active reasoning persona is derived from whichever option is Priority 1.

    Args:
        user_config: {"hierarchy": [str, str, str]} in user-defined priority order.
        casing_map: {name_lowercase: original_display_name} from fetch_existing_playlists.
        profiles:   {name_lowercase: list[{name, artist}]} from fetch_existing_playlists.
        allow_new_playlists: When False, injects a CRITICAL STRICT MODE block that
            forbids the model from inventing new playlist names.

    Returns:
        Fully interpolated system prompt string ready for the Groq API.

    Raises:
        KeyError: If "hierarchy" key is absent from user_config.
        IndexError: If hierarchy contains fewer than 3 elements.
    """
    # Filter out metadata-only priorities (Artist/Album) — they have no AI persona.
    h = [p for p in (user_config.get("hierarchy") or []) if p not in _METADATA_PRIORITIES]
    # Pad to 3 if user has fewer than 3 AI priorities active.
    while len(h) < 3:
        h.append(h[-1] if h else "Genre")

    # Resolve the active persona and vibe constraint from Priority 1.
    persona_desc = _PERSONA.get(
        h[0],
        "balanced — weigh genre, vibe, and activity equally",
    )

    vibe_constraint = _VIBE_CONSTRAINT.get(
        h[0],
        "CRITICAL: vibe_category must clearly reflect the Priority 1 category type.",
    )

    # Cap at 50 playlists — too many options degrades model classification quality.
    casing_items = list(casing_map.items())[:50]
    bio_lines = [
        f"  {_build_playlist_bio(display_name, profiles.get(key, []))}"
        for key, display_name in casing_items
    ]
    bios_block = "\n".join(bio_lines) if bio_lines else "  (none)"

    strict_mode_block = (
        f'STRICT: vibe_category must be an EXACT name from PLAYLISTS above. '
        f'No new names. No fit → REVIEW + vibe_category="{REVIEW_PLAYLIST_NAME}".\n'
    ) if not allow_new_playlists else ""

    vibe_category_hint = (
        "<exact playlist name from above>"
        if not allow_new_playlists
        else "<matching playlist name, or new descriptive category name>"
    )

    return f"""\
Music classifier. Analyze as: {persona_desc}.
PRIORITIES: 1={h[0]}  2={h[1]}  3={h[2]}
{vibe_constraint}
{strict_mode_block}
PLAYLISTS (name: artists [sample tracks]):
{bios_block}

RULES:
1. Evaluate priorities in order; fall to next only if no confident match.
2. Judge playlist fit by sonic profile (artists+tracks), not name alone.
3. Genre playlists need genre/cultural match. Activity/Mood: energy/use-case.
4. Prefer existing playlists; new names only on severe sonic mismatch.
5. confidence < {confidence_threshold} → action_recommendation="REVIEW".
6. vibe_category MUST be a genre/mood/activity CATEGORY (e.g. "J-Pop", "City Pop", "Late Night", "Workout"). NEVER use the track title, artist name, or album name as vibe_category.

JSON only: {{"primary_genre":"<str>","vibe_category":"{vibe_category_hint}","confidence_score":<1-100>,"action_recommendation":"<MATCH|REVIEW>","reasoning":"<≤10 words>"}}"""


# ---------------------------------------------------------------------------
# 3.6  RULE #4 — STRICT JSON
# ---------------------------------------------------------------------------
def classify_track(groq_client: Groq, system_prompt: str, track: dict) -> dict:
    """Classify a track via Groq and return a validated analysis dict.

    Uses response_format=json_object to enforce JSON output at the API level.
    Returns the fallback dict on any error — never raises.

    Args:
        groq_client: Authenticated Groq client.
        system_prompt: Pre-built prompt string from build_system_prompt().
        track: Dict with keys: name, artist, album.

    Returns:
        Dict with keys: primary_genre (str), vibe_category (str),
        confidence_score (int), action_recommendation (str).
        Returns _FALLBACK on any API or parse error.

    Raises:
        Nothing — all errors are caught and return the fallback.
    """
    hint = f"\n{track['hint']}" if track.get("hint") else ""
    try:
        resp = _groq_call(
            groq_client,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": (
                    f"Track: {track['name']} by {track['artist']} "
                    f"(Album: {track['album']}){hint}"
                )},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=150,
        )
        result = json.loads(resp.choices[0].message.content)
    except (APIError, APIConnectionError, RateLimitError, _TpdExhausted, json.JSONDecodeError) as exc:
        logger.warning("classify_track failed for '%s': %s", track.get("name"), exc)
        return _FALLBACK.copy()

    required: dict[str, type] = {
        "primary_genre": str,
        "vibe_category": str,
        "confidence_score": int,
        "action_recommendation": str,
        "reasoning": str,
    }
    for key, typ in required.items():
        if key not in result or not isinstance(result[key], typ):
            logger.warning("Malformed Groq response for '%s' — using fallback.", track.get("name"))
            return _FALLBACK.copy()

    return result


# ---------------------------------------------------------------------------
# 3.6b  BATCH CLASSIFICATION
# ---------------------------------------------------------------------------
def classify_batch(
    groq_client: Groq,
    system_prompt: str,
    tracks: list[dict],
) -> list[dict]:
    """Classify multiple tracks in a single Groq API call.

    Sends all tracks in one request to amortise system-prompt token cost and
    eliminate per-track sleep overhead. Falls back to individual classify_track
    calls if the model returns a malformed or wrong-length response.

    Args:
        groq_client: Authenticated Groq client.
        system_prompt: Pre-built prompt from build_system_prompt().
        tracks: List of track dicts (name, artist, album, optional hint).

    Returns:
        List of classification dicts in the same order as tracks.
        Any malformed individual result is replaced with _FALLBACK.
    """
    if len(tracks) == 1:
        return [classify_track(groq_client, system_prompt, tracks[0])]

    track_lines = []
    for i, t in enumerate(tracks):
        line = f'{i + 1}. "{t["name"]}" by {t["artist"]} (Album: {t["album"]})'
        if t.get("hint"):
            line += f" [{t['hint']}]"
        track_lines.append(line)

    required_keys: dict[str, type] = {
        "primary_genre": str,
        "vibe_category": str,
        "confidence_score": int,
        "action_recommendation": str,
        "reasoning": str,
    }

    def _validate(result: dict) -> dict:
        for key, typ in required_keys.items():
            val = result.get(key)
            if val is None:
                return _FALLBACK.copy()
            # confidence_score sometimes comes back as float
            if key == "confidence_score" and isinstance(val, float):
                result[key] = int(val)
            elif not isinstance(result[key], typ):
                return _FALLBACK.copy()
        return result

    user_msg = (
        f"Classify all {len(tracks)} tracks in order. "
        f"Return {{\"classifications\":[<{len(tracks)} objects>]}}.\n"
        + "\n".join(track_lines)
    )

    try:
        resp = _groq_call(
            groq_client,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=150 * len(tracks),
        )

        raw = json.loads(resp.choices[0].message.content)
        batch_results = raw.get("classifications")

        if not isinstance(batch_results, list) or len(batch_results) != len(tracks):
            logger.warning(
                "classify_batch: expected %d results, got %s — falling back to individual calls.",
                len(tracks),
                len(batch_results) if isinstance(batch_results, list) else type(batch_results).__name__,
            )
            return [classify_track(groq_client, system_prompt, t) for t in tracks]

        return [_validate(r) for r in batch_results]

    except (APIError, APIConnectionError, RateLimitError, _TpdExhausted, json.JSONDecodeError) as exc:
        logger.warning("classify_batch failed (%s) — falling back to individual calls.", exc)
        return [classify_track(groq_client, system_prompt, t) for t in tracks]


# ---------------------------------------------------------------------------
# 3.7  RULES #2 & #3
# ---------------------------------------------------------------------------
def resolve_destination(
    classification: dict,
    existing_playlists: dict,
    casing_map: dict,
    allow_new_playlists: bool = True,
    confidence_threshold: int = CONFIDENCE_THRESHOLD,
) -> tuple[str, str]:
    """Determine the destination playlist name and resolution type.

    Implements the exact 5-step logic flow from the spec, with an optional
    strict-mode guardrail at Step 5 that redirects new-playlist candidates
    to Review / Misc when allow_new_playlists is False.

    Args:
        classification: Result dict from classify_track().
        existing_playlists: {name_lowercase: playlist_id}.
        casing_map: {name_lowercase: original_display_name}.
        allow_new_playlists: When False, any track that would create a new
            playlist is redirected to Review / Misc instead.
        confidence_threshold: Minimum score to proceed with a MATCH decision.

    Returns:
        Tuple of (destination_playlist_name, resolution_type).
        resolution_type is one of: EXISTING, NEW, REVIEW.

    Raises:
        Nothing.
    """
    # Step 1 — confidence guardrail
    if classification.get("confidence_score", 0) < confidence_threshold:
        return (REVIEW_PLAYLIST_NAME, "REVIEW")

    # Step 2 — explicit REVIEW recommendation
    if classification.get("action_recommendation") == "REVIEW":
        return (REVIEW_PLAYLIST_NAME, "REVIEW")

    # Step 3 — normalise candidate; guard empty string to avoid blank playlist creation
    candidate = classification.get("vibe_category", "").strip().lower()
    if not candidate:
        return (REVIEW_PLAYLIST_NAME, "REVIEW")

    # Step 4 — match existing playlist (case-insensitive)
    if candidate in existing_playlists:
        return (casing_map[candidate], "EXISTING")

    # Step 5 — new playlist or strict-mode redirect
    if not allow_new_playlists:
        logger.info(
            "Strict Mode: '%s' would create '%s' — redirecting to Review / Misc.",
            classification.get("vibe_category"), REVIEW_PLAYLIST_NAME,
        )
        return (REVIEW_PLAYLIST_NAME, "REVIEW")

    return (classification.get("vibe_category", "").strip(), "NEW")


# ---------------------------------------------------------------------------
# 3.8
# ---------------------------------------------------------------------------
def get_or_create_playlist(
    sp: spotipy.Spotify,
    name: str,
    existing_playlists: dict,
    casing_map: dict,
    user_id: str,
) -> str:
    """Return the ID of an existing playlist, or create and cache a new one.

    Mutates existing_playlists and casing_map in-place after creation to
    prevent duplicate creation within the same run.

    Args:
        sp: Authenticated Spotipy client.
        name: Target playlist display name.
        existing_playlists: {name_lowercase: playlist_id} — mutated in place.
        casing_map: {name_lowercase: original_display_name} — mutated in place.
        user_id: Spotify user ID (kept for signature compatibility).

    Returns:
        Playlist ID string.

    Raises:
        RuntimeError: If playlist creation fails.
    """
    key = name.lower()
    if key in existing_playlists:
        return existing_playlists[key]

    logger.info("Creating new playlist: '%s'.", name)
    try:
        # NOTE: sp.user_playlist_create() uses the deprecated
        # /v1/users/{id}/playlists endpoint which returns 403 for third-party
        # apps. /v1/me/playlists via sp._post() is the working alternative.
        new_pl = _retry_spotify(sp._post, "me/playlists", payload={"name": name, "public": False})
        pid = new_pl["id"]
        existing_playlists[key] = pid
        casing_map[key] = name
        logger.info("Created playlist '%s' (id: %s).", name, pid)
        return pid
    except spotipy.SpotifyException as exc:
        raise RuntimeError(f"Failed to create playlist '{name}': {exc}") from exc


# ---------------------------------------------------------------------------
# 3.9
# ---------------------------------------------------------------------------
def add_track_to_playlist(
    sp: spotipy.Spotify,
    playlist_id: str,
    track_uri: str,
    uri_cache: dict[str, set[str]] | None = None,
) -> bool:
    """Add a track to a playlist, skipping silently if already present.

    On the first call for a given playlist_id, pages through all existing items
    and stores the URI set in uri_cache. Subsequent calls for the same playlist
    hit the cache instead of re-querying Spotify, reducing N×M API calls to N+M.

    Args:
        sp: Authenticated Spotipy client.
        playlist_id: Target Spotify playlist ID.
        track_uri: Spotify URI of the track to add.
        uri_cache: Shared {playlist_id: set(uri)} dict maintained by the caller.
            Pass None to disable caching (fetches fresh every call — legacy behaviour).

    Returns:
        True if the track was added, False if it was already present.

    Raises:
        spotipy.SpotifyException: On non-rate-limit Spotify errors.
    """
    # Populate cache on first encounter of this playlist.
    if uri_cache is not None and playlist_id not in uri_cache:
        fetched: set[str] = set()
        results = _retry_spotify(sp.playlist_items, playlist_id)
        if results:
            for item in results.get("items", []):
                t = item.get("track") or item.get("item") if item else None
                if t and t.get("uri"):
                    fetched.add(t["uri"])
            while results["next"]:
                results = _retry_spotify(sp.next, results)
                if results:
                    for item in results.get("items", []):
                        t = item.get("track") or item.get("item") if item else None
                        if t and t.get("uri"):
                            fetched.add(t["uri"])
        uri_cache[playlist_id] = fetched

    existing_uris: set[str] = (
        uri_cache[playlist_id] if uri_cache is not None
        else _fetch_all_playlist_uris(sp, playlist_id)
    )

    if track_uri in existing_uris:
        logger.info("Duplicate — skipping %s in playlist %s.", track_uri, playlist_id)
        return False

    _retry_spotify(sp.playlist_add_items, playlist_id, [track_uri])
    if uri_cache is not None:
        uri_cache[playlist_id].add(track_uri)  # keep cache consistent
    logger.info("Added %s to playlist %s.", track_uri, playlist_id)
    return True


def _fetch_all_playlist_uris(sp: spotipy.Spotify, playlist_id: str) -> set[str]:
    """Fetch every track URI from a playlist (no caching). Used as the no-cache fallback."""
    uris: set[str] = set()
    results = _retry_spotify(sp.playlist_items, playlist_id)
    if results:
        for item in results.get("items", []):
            t = item.get("track") or item.get("item") if item else None
            if t and t.get("uri"):
                uris.add(t["uri"])
        while results["next"]:
            results = _retry_spotify(sp.next, results)
            if results:
                for item in results.get("items", []):
                    t = item.get("track") or item.get("item") if item else None
                    if t and t.get("uri"):
                        uris.add(t["uri"])
    return uris


# ---------------------------------------------------------------------------
# INTERNAL HELPER — metadata-based destination (Artist / Album priorities)
# ---------------------------------------------------------------------------
def _resolve_metadata(
    track: dict,
    priority: str,
    existing: dict,
    casing: dict,
) -> tuple[str, str] | tuple[None, None]:
    """Return (dest_name, resolution_type) using track metadata, or (None, None) if unusable."""
    value = (track.get("artist") if priority == "Artist" else track.get("album", "")).strip()
    if not value or value.lower() in ("unknown", "unknown artist", "unknown album", ""):
        return None, None
    key = value.lower()
    if key in existing:
        return casing[key], "EXISTING"
    return value, "NEW"


# ---------------------------------------------------------------------------
# 3.10  PRIMARY ENTRYPOINT
# ---------------------------------------------------------------------------
def run_sorter(
    user_config: dict,
    limit: int,
    remove_from_liked: bool = True,
    allow_new_playlists: bool = True,
    progress_callback=None,
    dry_run: bool = False,
    confidence_threshold: int = CONFIDENCE_THRESHOLD,
) -> list[dict]:
    """Classify and sort Liked Songs into playlists.

    Args:
        user_config: {"hierarchy": [str, str, str]} — user-defined priority.
        limit: Maximum number of liked tracks to process.
        remove_from_liked: When True, each successfully placed track is removed
            from Liked Songs so it won't be re-processed next run.
        allow_new_playlists: When False (Strict Mode), tracks that would create a
            new playlist are redirected to Review / Misc instead.
        progress_callback: Optional callable(current, total, track_name).
        dry_run: When True, classify tracks but skip all Spotify writes.
            Logs show "Preview → dest" statuses.
        confidence_threshold: Minimum confidence score to accept a MATCH decision.

    Returns:
        List of log entry dicts.

    Raises:
        RuntimeError: On auth or setup failures (propagated before the loop).
    """
    sp = get_spotify_client()
    groq_client = get_groq_client()
    user_id = _retry_spotify(sp.current_user)["id"]

    try:
        existing_playlists, casing_map, profiles = fetch_existing_playlists(
            sp, user_id=user_id
        )
        if not dry_run:
            # Ensure "Review / Misc" exists up front — NEVER create on-demand in loop.
            get_or_create_playlist(
                sp, REVIEW_PLAYLIST_NAME, existing_playlists, casing_map, user_id
            )
    except (spotipy.SpotifyException, RuntimeError) as exc:
        if not dry_run:
            raise
        logger.warning(
            "fetch_existing_playlists failed (%s) — dry run will proceed without playlist context.", exc
        )
        existing_playlists, casing_map, profiles = {}, {}, {}

    tracks = fetch_liked_tracks(sp, limit)
    system_prompt = build_system_prompt(
        user_config, casing_map, profiles,
        allow_new_playlists=allow_new_playlists,
        confidence_threshold=confidence_threshold,
    )

    if not tracks:
        logger.info("No liked tracks found — nothing to sort.")
        return []

    # Shared URI cache: populated once per playlist, reused for all subsequent
    # dedup checks within this run — avoids N×M pagination overhead.
    uri_cache: dict[str, set[str]] = {}
    artist_destinations: dict[str, str] = {}
    liked_ids_to_delete: list[str] = []  # batched at end — N→ceil(N/50) Spotify calls

    logs: list[dict] = []
    total = len(tracks)

    for batch_start in range(0, total, BATCH_SIZE):
        batch = tracks[batch_start:batch_start + BATCH_SIZE]

        # Inject artist-affinity hints before classification
        enriched: list[dict] = []
        for t in batch:
            artist_key = t["artist"].strip().lower()
            if artist_key and artist_key != "unknown" and artist_key in artist_destinations:
                t = {
                    **t,
                    "hint": (
                        f"Route to '{artist_destinations[artist_key]}' for consistency "
                        f"(same artist as a previously sorted track)."
                    ),
                }
            enriched.append(t)

        # Fire progress for first track in batch
        if progress_callback:
            try:
                progress_callback(batch_start + 1, total, enriched[0]["name"])
            except Exception:
                pass

        classifications = classify_batch(groq_client, system_prompt, enriched)

        # Sleep between batches only — not between every track
        if batch_start + BATCH_SIZE < total:
            time.sleep(2.5)

        casing_len_before_batch = len(casing_map)

        for i, (track, classification) in enumerate(zip(enriched, classifications)):
            idx = batch_start + i
            if progress_callback and i > 0:
                try:
                    progress_callback(idx + 1, total, track["name"])
                except Exception:
                    pass

            try:
                artist_key = track["artist"].strip().lower()
                priorities = user_config["hierarchy"]

                if priorities[0] in _METADATA_PRIORITIES:
                    dest_name, res_type = _resolve_metadata(track, priorities[0], existing_playlists, casing_map)
                    if not dest_name:
                        dest_name, res_type = REVIEW_PLAYLIST_NAME, "REVIEW"
                else:
                    dest_name, res_type = resolve_destination(
                        classification, existing_playlists, casing_map,
                        allow_new_playlists, confidence_threshold,
                    )
                    if res_type == "REVIEW":
                        for p in priorities[1:3]:
                            if p in _METADATA_PRIORITIES:
                                md_dest, md_res = _resolve_metadata(track, p, existing_playlists, casing_map)
                                if md_dest:
                                    dest_name, res_type = md_dest, md_res
                                    break

                if res_type in ("EXISTING", "NEW") and artist_key and artist_key != "unknown":
                    artist_destinations[artist_key] = dest_name

                if dry_run:
                    status = f"Preview → {dest_name}"
                else:
                    playlist_id = get_or_create_playlist(
                        sp, dest_name, existing_playlists, casing_map, user_id
                    )
                    added = add_track_to_playlist(sp, playlist_id, track["uri"], uri_cache)

                    if remove_from_liked and added:
                        liked_ids_to_delete.append(track["id"])

                    if added:
                        status = (
                            f"Moved to {dest_name}"
                            if remove_from_liked
                            else f"Copied to {dest_name}"
                        )
                    else:
                        status = "Skipped (duplicate)"

                logs.append({
                    "track":       track["name"],
                    "artist":      track["artist"],
                    "genre":       classification["primary_genre"],
                    "vibe":        classification["vibe_category"],
                    "confidence":  classification["confidence_score"],
                    "reasoning":   classification["reasoning"],
                    "destination": dest_name,
                    "resolution":  res_type,
                    "status":      status,
                    "image_url":   track.get("image_url"),
                })
            except Exception as exc:
                logger.error("Failed to sort '%s': %s", track.get("name"), exc)
                logs.append({
                    "track":       track.get("name", "?"),
                    "artist":      track.get("artist", "?"),
                    "genre":       "-",
                    "vibe":        "-",
                    "confidence":  0,
                    "reasoning":   "-",
                    "destination": "-",
                    "resolution":  "ERROR",
                    "status":      f"ERROR: {exc}",
                    "image_url":   track.get("image_url"),
                })

        # Rebuild system prompt after the batch if new playlists were created,
        # so the next batch's classifications know those playlists exist.
        if not dry_run and len(casing_map) > casing_len_before_batch:
            system_prompt = build_system_prompt(
                user_config, casing_map, profiles,
                allow_new_playlists=allow_new_playlists,
                confidence_threshold=confidence_threshold,
            )
            logger.info("System prompt rebuilt after batch (new playlists created).")

    # Batch-delete liked tracks — ceil(N/50) calls instead of N calls.
    if liked_ids_to_delete:
        for i in range(0, len(liked_ids_to_delete), 50):
            _retry_spotify(sp.current_user_saved_tracks_delete, liked_ids_to_delete[i:i + 50])
        logger.info("Removed %d tracks from Liked Songs in %d batch(es).",
                    len(liked_ids_to_delete), -(-len(liked_ids_to_delete) // 50))

    return logs


# ---------------------------------------------------------------------------
# EDGE CASE LAB — 4.1  Find the Review / Misc playlist
# ---------------------------------------------------------------------------
def get_review_playlist_id(sp: spotipy.Spotify, user_id: str | None = None) -> str | None:
    """Scan the authenticated user's owned playlists for Review / Misc.

    Args:
        sp: Authenticated Spotipy client.
        user_id: If provided, only match playlists owned by this user ID.

    Returns:
        Playlist ID string, or None if the playlist doesn't exist yet.
    """
    target = REVIEW_PLAYLIST_NAME.lower()
    results = _retry_spotify(sp.current_user_playlists, limit=50)
    while True:
        for item in results["items"]:
            if item is None:
                continue
            if user_id and item.get("owner", {}).get("id") != user_id:
                continue
            if item["name"].lower() == target:
                return item["id"]
        if not results["next"]:
            return None
        results = _retry_spotify(sp.next, results)


# ---------------------------------------------------------------------------
# EDGE CASE LAB — 4.2  Fetch tracks from the Review playlist
# ---------------------------------------------------------------------------
def fetch_review_tracks(
    sp: spotipy.Spotify,
    playlist_id: str,
    limit: int = 50,
) -> list[dict]:
    """Fetch up to `limit` tracks from the Review / Misc playlist.

    Args:
        sp: Authenticated Spotipy client.
        playlist_id: ID of the Review / Misc playlist.
        limit: Maximum number of tracks to return (default 50).

    Returns:
        List of {id, name, artist, album, uri} dicts.

    Raises:
        spotipy.SpotifyException: On API errors, so callers can surface them.
    """
    tracks: list[dict] = []
    result = _retry_spotify(sp.playlist_items, playlist_id, limit=min(limit, 50))
    if not result:
        return []

    while result and len(tracks) < limit:
        for item in result.get("items", []):
            if item is None:
                continue
            # Spotify returns the track object under "track" or "item" depending on API context
            t = item.get("track") or item.get("item")
            if not t or not t.get("id"):
                continue
            images = t.get("album", {}).get("images", [])
            tracks.append({
                "id":        t["id"],
                "name":      t["name"],
                "artist":    t["artists"][0]["name"] if t.get("artists") else "Unknown",
                "album":     t["album"]["name"] if t.get("album") else "Unknown",
                "uri":       t["uri"],
                "image_url": images[-1]["url"] if images else None,
            })
            if len(tracks) >= limit:
                break
        if result.get("next") and len(tracks) < limit:
            result = _retry_spotify(sp.next, result)
        else:
            break

    return tracks


# ---------------------------------------------------------------------------
# EDGE CASE LAB — 4.3  Groq analysis for a single Review track
# ---------------------------------------------------------------------------
_FALLBACK_ANALYSIS: dict = {
    "reasoning": "Could not analyze — API error.",
    "suggested_existing": REVIEW_PLAYLIST_NAME,
    "suggested_new": "Unsorted Gems",
}


def analyze_edge_case(
    groq_client: Groq,
    track: dict,
    casing_map: dict,
    profiles: dict,
    same_artist_tracks: list[str] | None = None,
) -> dict:
    """Call Groq to explain why a track is hard to sort and suggest destinations.

    Args:
        groq_client: Authenticated Groq client.
        track: Dict with keys: name, artist, album.
        casing_map: {name_lowercase: display_name} of existing playlists.
        profiles: {name_lowercase: list[{name, artist}]} from fetch_existing_playlists.

    Returns:
        Dict with keys: reasoning (str), suggested_existing (str), suggested_new (str).
        Returns _FALLBACK_ANALYSIS on any error — never raises.
    """
    review_lower = REVIEW_PLAYLIST_NAME.lower()
    bio_lines = []
    actual_playlist_names = []
    for key, display_name in casing_map.items():
        if key == review_lower:
            continue
        bio_lines.append(f"  • {_build_playlist_bio(display_name, profiles.get(key, []))}")
        actual_playlist_names.append(display_name)

    bios_block = "\n".join(bio_lines) if bio_lines else "  (none — no existing playlists)"

    artist_block = ""
    if same_artist_tracks:
        others_str = ", ".join(f'"{t}"' for t in same_artist_tracks)
        artist_block = (
            f"GROUP: same artist also has {others_str} in review — "
            f"suggest the SAME suggested_new name for all.\n"
        )

    valid_str = ", ".join(actual_playlist_names) if actual_playlist_names else "none"
    system_prompt = f"""\
Music librarian. Track failed auto-sort — analyze why.
VALID: {valid_str}
PROFILES:
{bios_block}
{artist_block}
1. suggested_existing: EXACT name from VALID, or "NONE".
2. reasoning: specific sonic reason (≤12 words, no generic phrases).
3. suggested_new: a genre/mood/activity CATEGORY name (e.g. "J-Pop", "City Pop", "Late Night Drives", "Bedroom Pop") — NEVER the track title, artist name, or album name.

JSON only: {{"reasoning":"<≤12 words>","suggested_existing":"<exact or NONE>","suggested_new":"<category name>"}}"""

    user_msg = f"Track: {track['name']} by {track['artist']} (Album: {track['album']})"
    try:
        resp = _groq_call(
            groq_client,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=120,
        )
        result = json.loads(resp.choices[0].message.content)
    except (APIError, APIConnectionError, RateLimitError, _TpdExhausted, json.JSONDecodeError) as exc:
        logger.warning("analyze_edge_case failed for '%s': %s", track.get("name"), exc)
        return _FALLBACK_ANALYSIS.copy()

    required = {"reasoning": str, "suggested_existing": str, "suggested_new": str}
    for key, typ in required.items():
        if key not in result or not isinstance(result[key], typ):
            logger.warning("Malformed analysis response for '%s'.", track.get("name"))
            return _FALLBACK_ANALYSIS.copy()

    # Python-level guardrail: reject any suggested_existing that isn't in the
    # actual playlist list — the model can hallucinate even with explicit instructions.
    raw_suggestion = result["suggested_existing"].strip()
    valid_names_lower = {name.lower(): name for name in actual_playlist_names}
    if raw_suggestion.upper() == "NONE" or raw_suggestion == "":
        result["suggested_existing"] = "NONE"
    elif raw_suggestion.lower() in valid_names_lower:
        # Normalise to the canonical display name
        result["suggested_existing"] = valid_names_lower[raw_suggestion.lower()]
    else:
        logger.warning(
            "analyze_edge_case: model hallucinated playlist '%s' for '%s' — forcing NONE.",
            raw_suggestion, track.get("name"),
        )
        result["suggested_existing"] = "NONE"

    return result


ECL_BATCH_SIZE: int = 5  # ECL responses are richer; smaller batches than sorter


def analyze_edge_case_batch(
    groq_client: Groq,
    tracks: list[dict],
    casing_map: dict,
    profiles: dict,
    artist_track_names: dict,
) -> list[dict]:
    """Analyze multiple review tracks in a single Groq API call.

    Falls back to individual analyze_edge_case calls if the response is
    malformed or has the wrong length.
    """
    if len(tracks) == 1:
        artist_key = tracks[0]["artist"].strip().lower()
        others = [n for n in artist_track_names.get(artist_key, []) if n != tracks[0]["name"]]
        return [analyze_edge_case(
            groq_client, tracks[0], casing_map, profiles,
            same_artist_tracks=others or None,
        )]

    review_lower = REVIEW_PLAYLIST_NAME.lower()
    bio_lines = []
    actual_playlist_names = []
    for key, display_name in casing_map.items():
        if key == review_lower:
            continue
        bio_lines.append(f"  {_build_playlist_bio(display_name, profiles.get(key, []))}")
        actual_playlist_names.append(display_name)

    bios_block = "\n".join(bio_lines) if bio_lines else "  (none)"

    valid_str = ", ".join(actual_playlist_names) if actual_playlist_names else "none"
    system_prompt = f"""\
Music librarian. Tracks failed auto-sort — analyze each.
VALID: {valid_str}
PROFILES:
{bios_block}
1. suggested_existing: EXACT name from VALID, or "NONE".
2. reasoning: specific sonic reason (≤12 words, no generic phrases).
3. suggested_new: a genre/mood/activity CATEGORY name (e.g. "J-Pop", "City Pop", "Late Night Drives") — NEVER the track title, artist, or album. Same artist → same category name.

JSON only: {{"analyses":[{{"reasoning":"...","suggested_existing":"...","suggested_new":"..."}}]}}"""

    track_lines = []
    for i, t in enumerate(tracks):
        artist_key = t["artist"].strip().lower()
        others = [n for n in artist_track_names.get(artist_key, []) if n != t["name"]]
        line = f'{i + 1}. "{t["name"]}" by {t["artist"]} (Album: {t["album"]})'
        if others:
            line += f' [same artist: {", ".join(others)}]'
        track_lines.append(line)

    valid_names_lower = {name.lower(): name for name in actual_playlist_names}

    def _validate_analysis(r: dict) -> dict:
        if not all(isinstance(r.get(k), str) for k in ("reasoning", "suggested_existing", "suggested_new")):
            return _FALLBACK_ANALYSIS.copy()
        raw = r["suggested_existing"].strip()
        if raw.upper() == "NONE" or not raw:
            r["suggested_existing"] = "NONE"
        elif raw.lower() in valid_names_lower:
            r["suggested_existing"] = valid_names_lower[raw.lower()]
        else:
            r["suggested_existing"] = "NONE"
        return r

    ecl_user_msg = (
        f"Analyze all {len(tracks)} tracks. "
        f"Return {{\"analyses\":[<{len(tracks)} objects in order>]}}.\n"
        + "\n".join(track_lines)
    )

    try:
        resp = _groq_call(
            groq_client,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": ecl_user_msg},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=180 * len(tracks),
        )
        raw = json.loads(resp.choices[0].message.content)
        results = raw.get("analyses", [])

        if not isinstance(results, list) or len(results) != len(tracks):
            logger.warning(
                "analyze_edge_case_batch: expected %d results, got %s — falling back.",
                len(tracks), len(results) if isinstance(results, list) else "?",
            )
            raise ValueError("wrong length")

        return [_validate_analysis(r) for r in results]

    except Exception as exc:
        logger.warning("analyze_edge_case_batch failed (%s) — falling back to individual calls.", exc)
        out = []
        for i, t in enumerate(tracks):
            artist_key = t["artist"].strip().lower()
            others = [n for n in artist_track_names.get(artist_key, []) if n != t["name"]]
            out.append(analyze_edge_case(
                groq_client, t, casing_map, profiles,
                same_artist_tracks=others or None,
            ))
            if i < len(tracks) - 1:
                time.sleep(2.5)
        return out


# ---------------------------------------------------------------------------
# EDGE CASE LAB — 4.4  Orchestrator: load + analyze all Review tracks
# ---------------------------------------------------------------------------
def load_edge_case_lab() -> dict:
    """Fetch Review / Misc tracks and run Groq analysis on each.

    Builds Spotify and Groq clients internally. Fetches the user's owned
    playlists for sonic context, then retrieves up to 20 tracks from
    Review / Misc and calls analyze_edge_case for each one.

    A 2.5 s sleep is inserted between Groq calls to respect the free-tier
    rate limit.

    Returns:
        Dict with keys:
          tracks     — list[dict]  tracks currently in Review / Misc
          analyses   — {uri: {reasoning, suggested_existing, suggested_new}}
          review_pid — str  Review / Misc playlist ID (empty string if absent)
          existing   — {name_lower: id}
          casing     — {name_lower: display_name}
          user_id    — str

    Raises:
        RuntimeError: On Spotify or Groq auth failure.
    """
    sp = get_spotify_client()
    groq_client = get_groq_client()
    user_id = _retry_spotify(sp.current_user)["id"]

    existing_playlists, casing_map, profiles = fetch_existing_playlists(
        sp, user_id=user_id
    )

    review_pid = get_review_playlist_id(sp, user_id=user_id) or ""
    if not review_pid:
        logger.info("Review / Misc playlist not found — nothing to load.")
        return {
            "tracks":     [],
            "analyses":   {},
            "review_pid": "",
            "existing":   existing_playlists,
            "casing":     casing_map,
            "user_id":    user_id,
        }

    tracks = fetch_review_tracks(sp, review_pid)

    artist_track_names: dict[str, list[str]] = defaultdict(list)
    for t in tracks:
        key = t["artist"].strip().lower()
        if key and key != "unknown":
            artist_track_names[key].append(t["name"])

    analyses: dict[str, dict] = {}
    for batch_start in range(0, len(tracks), ECL_BATCH_SIZE):
        batch = tracks[batch_start:batch_start + ECL_BATCH_SIZE]
        results = analyze_edge_case_batch(groq_client, batch, casing_map, profiles, artist_track_names)
        for track, result in zip(batch, results):
            analyses[track["uri"]] = result
        if batch_start + ECL_BATCH_SIZE < len(tracks):
            time.sleep(2.5)

    logger.info("Edge Case Lab loaded %d tracks with analyses.", len(tracks))
    return {
        "tracks":     tracks,
        "analyses":   analyses,
        "review_pid": review_pid,
        "existing":   existing_playlists,
        "casing":     casing_map,
        "user_id":    user_id,
    }


# ---------------------------------------------------------------------------
# EDGE CASE LAB — 4.5  Execute a single move action from the Review playlist
# ---------------------------------------------------------------------------
def execute_move_from_review(
    track_uri: str,
    target_name: str,
    review_pid: str,
    existing_playlists: dict,
    casing_map: dict,
    user_id: str,
) -> tuple[bool, str, bool]:
    """Move a track from Review / Misc to target_name.

    Applies smart routing: if target_name (case-insensitive, stripped) matches
    an existing playlist, routes there silently instead of creating a duplicate.
    Creates a new playlist only when no match is found.
    Mutates existing_playlists and casing_map in-place when a new playlist
    is created, so the caller's session-state dicts stay current.

    Args:
        track_uri: Spotify URI of the track to move.
        target_name: Display name of the destination playlist (may be user-typed).
        review_pid: ID of the Review / Misc playlist.
        existing_playlists: {name_lower: id} — mutated in-place on creation.
        casing_map: {name_lower: display_name} — mutated in-place on creation.
        user_id: Spotify user ID.

    Returns:
        Tuple of (success: bool, dest_display_name: str, created_new: bool).
        created_new is True when a new Spotify playlist was created, False when
        routed to an existing one. On failure, returns (False, "", False).
    """
    try:
        sp = get_spotify_client()
        # Smart routing: check for a case-insensitive match BEFORE creating.
        # get_or_create_playlist also does this, but we need the flag here.
        normalized = target_name.strip().lower()
        created_new = normalized not in existing_playlists

        playlist_id = get_or_create_playlist(
            sp, target_name.strip(), existing_playlists, casing_map, user_id
        )
        _retry_spotify(sp.playlist_add_items, playlist_id, [track_uri])
        _retry_spotify(
            sp.playlist_remove_all_occurrences_of_items,
            review_pid,
            [track_uri],
        )
        dest_display = casing_map.get(normalized, target_name.strip())
        logger.info(
            "Moved %s from Review to '%s' (%s).",
            track_uri, dest_display, "new" if created_new else "existing",
        )
        return True, dest_display, created_new
    except Exception as exc:
        logger.error("execute_move_from_review failed: %s", exc)
        return False, "", False


# ---------------------------------------------------------------------------
# LOCAL FILES — constants
# ---------------------------------------------------------------------------
LOCAL_FORMATS: frozenset[str] = frozenset(
    {".mp3", ".flac", ".m4a", ".ogg", ".wav", ".opus", ".aac"}
)
LOCAL_REVIEW_FOLDER: str = "Review"


# ---------------------------------------------------------------------------
# LOCAL FILES — 5.1  Browse a directory
# ---------------------------------------------------------------------------
def browse_directory(path: str) -> dict:
    """Return subdirectories and audio-file count for the given path.

    Args:
        path: Absolute path to inspect.

    Returns:
        Dict with keys: current (str), parent (str | None),
        dirs (list[{name, path, audio_count}]), audio_count (int).
    """
    resolved = Path(path).resolve()
    parent = str(resolved.parent) if resolved != resolved.parent else None

    dirs: list[dict] = []
    audio_count = 0

    try:
        for entry in os.scandir(str(resolved)):
            if entry.is_dir(follow_symlinks=False):
                try:
                    sub_audio = sum(
                        1 for f in os.scandir(entry.path)
                        if f.is_file()
                        and os.path.splitext(f.name)[1].lower() in LOCAL_FORMATS
                    )
                except OSError:
                    sub_audio = 0
                dirs.append({"name": entry.name, "path": entry.path, "audio_count": sub_audio})
            elif entry.is_file() and os.path.splitext(entry.name)[1].lower() in LOCAL_FORMATS:
                audio_count += 1
    except OSError as exc:
        logger.warning("browse_directory error for '%s': %s", path, exc)

    dirs.sort(key=lambda d: d["name"].lower())
    return {
        "current": str(resolved),
        "parent": parent,
        "dirs": dirs,
        "audio_count": audio_count,
    }


# ---------------------------------------------------------------------------
# LOCAL FILES — 5.2  Scan audio files in a folder (non-recursive)
# ---------------------------------------------------------------------------
def scan_local_tracks(folder_path: str, limit: int = 200) -> list[dict]:
    """Scan folder for audio files and read their metadata tags.

    Only scans the immediate directory — subfolders are treated as playlists.

    Args:
        folder_path: Absolute path to the folder to scan.
        limit: Maximum number of tracks to return.

    Returns:
        List of dicts with keys: id, path, name, artist, album, uri (=path),
        format, duration_ms.
    """
    folder_path = str(Path(folder_path).resolve())
    if not os.path.isdir(folder_path):
        logger.warning("scan_local_tracks: not a directory: '%s'", folder_path)
        return []

    tracks: list[dict] = []
    try:
        all_entries = (
            e for e in os.scandir(folder_path)
            if e.is_file() and os.path.splitext(e.name)[1].lower() in LOCAL_FORMATS
        )
        entries = list(itertools.islice(all_entries, limit))
    except OSError as exc:
        logger.error("scan_local_tracks: cannot read '%s': %s", folder_path, exc)
        return []

    for entry in entries:
        path = entry.path
        suffix = os.path.splitext(entry.name)[1].lower()
        ext = suffix.lstrip(".")
        name = os.path.splitext(entry.name)[0]
        artist = "Unknown"
        album = "Unknown"
        duration_ms: int | None = None

        try:
            audio = mutagen.File(path, easy=True)
            if audio:
                if audio.get("title"):
                    name = audio["title"][0]
                if audio.get("artist"):
                    artist = audio["artist"][0]
                if audio.get("album"):
                    album = audio["album"][0]
                if hasattr(audio, "info") and audio.info:
                    duration_ms = int(audio.info.length * 1000)
        except Exception as exc:
            logger.warning("Could not read metadata for '%s': %s", path, exc)

        track_id = hashlib.sha1(path.encode()).hexdigest()[:16]
        tracks.append({
            "id":          track_id,
            "path":        path,
            "name":        name,
            "artist":      artist,
            "album":       album,
            "uri":         path,
            "format":      ext,
            "duration_ms": duration_ms,
        })

    return tracks


# ---------------------------------------------------------------------------
# LOCAL FILES — 5.3  Subfolder-as-playlist helpers
# ---------------------------------------------------------------------------
def fetch_local_playlists(folder_path: str) -> tuple[dict, dict]:
    """Return existing subfolders as 'playlists'.

    Args:
        folder_path: Root folder whose immediate subdirectories are playlists.

    Returns:
        Tuple of:
          existing — {name_lowercase: absolute_folder_path}
          casing   — {name_lowercase: display_name}
    """
    existing: dict[str, str] = {}
    casing: dict[str, str] = {}
    try:
        for entry in os.scandir(folder_path):
            if entry.is_dir(follow_symlinks=False):
                key = entry.name.lower()
                existing[key] = entry.path
                casing[key] = entry.name
    except OSError as exc:
        logger.warning("fetch_local_playlists error: %s", exc)
    return existing, casing


def get_or_create_local_folder(
    base_path: str,
    name: str,
    existing: dict,
    casing: dict,
) -> str:
    """Return path to a named subfolder, creating it if absent.

    Mutates existing and casing in-place on creation.

    Args:
        base_path: Root folder.
        name: Desired subfolder display name.
        existing: {name_lower: path} — mutated in-place.
        casing: {name_lower: display_name} — mutated in-place.

    Returns:
        Absolute path to the (possibly newly created) subfolder.
    """
    key = name.lower()
    if key in existing:
        return existing[key]
    folder_path = os.path.join(base_path, name)
    os.makedirs(folder_path, exist_ok=True)
    existing[key] = folder_path
    casing[key] = name
    logger.info("Created local folder '%s'.", name)
    return folder_path


# ---------------------------------------------------------------------------
# LOCAL FILES — 5.4  Generate an M3U playlist file
# ---------------------------------------------------------------------------
def generate_m3u(base_path: str, folder_name: str, entries: list[dict]) -> str:
    """Write an M3U file for a sorted destination folder.

    Args:
        base_path: Root folder (M3U is written here).
        folder_name: Name of the destination subfolder (used for file name + paths).
        entries: List of track dicts; each must have dest_path, name, artist,
                 and optionally duration_ms.

    Returns:
        Absolute path to the written M3U file.
    """
    m3u_path = os.path.join(base_path, f"{folder_name}.m3u")
    lines = ["#EXTM3U"]
    for entry in entries:
        duration = int((entry.get("duration_ms") or 0) / 1000)
        artist = entry.get("artist", "Unknown")
        title = entry.get("name", "Unknown")
        lines.append(f"#EXTINF:{duration},{artist} - {title}")
        rel = os.path.join(folder_name, os.path.basename(entry.get("dest_path", "")))
        lines.append(rel)
    with open(m3u_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    logger.info("Generated M3U: %s", m3u_path)
    return m3u_path


# ---------------------------------------------------------------------------
# LOCAL FILES — 5.5  Run the local auto-sorter
# ---------------------------------------------------------------------------
def run_local_sorter(
    folder_path: str,
    user_config: dict,
    limit: int,
    allow_new_folders: bool = True,
    progress_callback=None,
    dry_run: bool = False,
    confidence_threshold: int = CONFIDENCE_THRESHOLD,
) -> list[dict]:
    """Classify and sort local audio files into subfolders.

    Mirrors run_sorter() but operates on the filesystem instead of Spotify.

    Args:
        folder_path: Root folder containing the audio files to sort.
        user_config: {"hierarchy": [str, str, str]} — user priority order.
        limit: Maximum number of files to process.
        allow_new_folders: When False, files are redirected to Review instead
            of creating new subfolders.
        progress_callback: Optional callable(current, total, track_name).
        dry_run: When True, classify but skip all filesystem writes.
        confidence_threshold: Minimum confidence score to accept a MATCH.

    Returns:
        List of log-entry dicts (same schema as run_sorter).
    """
    folder_path = str(Path(folder_path).resolve())
    if not os.path.isdir(folder_path):
        logger.error("run_local_sorter: not a directory: '%s'", folder_path)
        return []

    groq_client = get_groq_client()
    existing, casing = fetch_local_playlists(folder_path)
    tracks = scan_local_tracks(folder_path, limit)

    if not tracks:
        logger.info("No audio files found in '%s'.", folder_path)
        return []

    profiles: dict = {}  # no sonic profiling for local folders
    system_prompt = build_system_prompt(
        user_config, casing, profiles,
        allow_new_playlists=allow_new_folders,
        confidence_threshold=confidence_threshold,
    )

    if not dry_run:
        get_or_create_local_folder(folder_path, LOCAL_REVIEW_FOLDER, existing, casing)

    dest_entries: dict[str, list[dict]] = {}
    artist_destinations: dict[str, str] = {}
    logs: list[dict] = []
    total = len(tracks)

    for batch_start in range(0, total, BATCH_SIZE):
        batch = tracks[batch_start:batch_start + BATCH_SIZE]

        enriched: list[dict] = []
        for t in batch:
            artist_key = t["artist"].strip().lower()
            if artist_key and artist_key != "unknown" and artist_key in artist_destinations:
                t = {
                    **t,
                    "hint": (
                        f"Route to '{artist_destinations[artist_key]}' for consistency "
                        f"(same artist as a previously sorted track)."
                    ),
                }
            enriched.append(t)

        if progress_callback:
            try:
                progress_callback(batch_start + 1, total, enriched[0]["name"])
            except Exception:
                pass

        classifications = classify_batch(groq_client, system_prompt, enriched)

        if batch_start + BATCH_SIZE < total:
            time.sleep(2.5)

        casing_len_before_batch = len(casing)

        for i, (track, classification) in enumerate(zip(enriched, classifications)):
            idx = batch_start + i
            if progress_callback and i > 0:
                try:
                    progress_callback(idx + 1, total, track["name"])
                except Exception:
                    pass

            try:
                artist_key = track["artist"].strip().lower()
                priorities = user_config["hierarchy"]

                # P1 = Artist/Album: resolve directly from metadata, skip AI result
                if priorities[0] in _METADATA_PRIORITIES:
                    dest_name, res_type = _resolve_metadata(track, priorities[0], existing, casing)
                    if not dest_name:
                        dest_name, res_type = LOCAL_REVIEW_FOLDER, "REVIEW"
                else:
                    dest_name, res_type = resolve_destination(
                        classification, existing, casing,
                        allow_new_folders, confidence_threshold,
                    )
                    # AI routed to Review — try metadata fallback at P2/P3
                    if res_type == "REVIEW":
                        for p in priorities[1:3]:
                            if p in _METADATA_PRIORITIES:
                                md_dest, md_res = _resolve_metadata(track, p, existing, casing)
                                if md_dest:
                                    dest_name, res_type = md_dest, md_res
                                    break

                if dest_name == REVIEW_PLAYLIST_NAME:
                    dest_name = LOCAL_REVIEW_FOLDER
                    res_type = "REVIEW"

                if res_type in ("EXISTING", "NEW") and artist_key and artist_key != "unknown":
                    artist_destinations[artist_key] = dest_name

                if dry_run:
                    status = f"Preview → {dest_name}"
                else:
                    dest_folder = get_or_create_local_folder(
                        folder_path, dest_name, existing, casing
                    )
                    dest_filename = os.path.basename(track["path"])
                    dest_filepath = os.path.join(dest_folder, dest_filename)

                    if os.path.exists(dest_filepath):
                        status = "Skipped (duplicate)"
                    else:
                        shutil.move(track["path"], dest_filepath)
                        status = f"Moved to {dest_name}"
                        dest_entries.setdefault(dest_name, []).append(
                            {**track, "dest_path": dest_filepath}
                        )

                logs.append({
                    "track":       track["name"],
                    "artist":      track["artist"],
                    "genre":       classification["primary_genre"],
                    "vibe":        classification["vibe_category"],
                    "confidence":  classification["confidence_score"],
                    "reasoning":   classification["reasoning"],
                    "destination": dest_name,
                    "resolution":  res_type,
                    "status":      status,
                    "image_url":   None,
                })
            except Exception as exc:
                logger.error("Failed to sort '%s': %s", track.get("name"), exc)
                logs.append({
                    "track":       track.get("name", "?"),
                    "artist":      track.get("artist", "?"),
                    "genre":       "-",
                    "vibe":        "-",
                    "confidence":  0,
                    "reasoning":   "-",
                    "destination": "-",
                    "resolution":  "ERROR",
                    "status":      f"ERROR: {exc}",
                    "image_url":   None,
                })

        if not dry_run and len(casing) > casing_len_before_batch:
            system_prompt = build_system_prompt(
                user_config, casing, profiles,
                allow_new_playlists=allow_new_folders,
                confidence_threshold=confidence_threshold,
            )
            logger.info("System prompt rebuilt after batch (new folders created).")

    return logs


# ---------------------------------------------------------------------------
# LOCAL FILES — 5.6  Load the Local Edge Case Lab
# ---------------------------------------------------------------------------
def load_local_edge_case_lab(folder_path: str) -> dict:
    """Load tracks from the Review subfolder and run Groq analysis on each.

    Args:
        folder_path: Root folder (must contain a 'Review' subfolder).

    Returns:
        Dict with keys: tracks, analyses, review_folder, existing, casing,
        base_path.
    """
    folder_path = str(Path(folder_path).resolve())
    review_folder = os.path.join(folder_path, LOCAL_REVIEW_FOLDER)
    existing, casing = fetch_local_playlists(folder_path)

    if not os.path.isdir(review_folder):
        return {
            "tracks":        [],
            "analyses":      {},
            "review_folder": review_folder,
            "existing":      existing,
            "casing":        casing,
            "base_path":     folder_path,
        }

    groq_client = get_groq_client()
    tracks = scan_local_tracks(review_folder, limit=20)

    # Exclude the Review folder itself from analysis suggestions
    casing_for_analysis = {
        k: v for k, v in casing.items()
        if k != LOCAL_REVIEW_FOLDER.lower()
    }

    artist_track_names: dict[str, list[str]] = defaultdict(list)
    for t in tracks:
        key = t["artist"].strip().lower()
        if key and key != "unknown":
            artist_track_names[key].append(t["name"])

    analyses: dict[str, dict] = {}
    for batch_start in range(0, len(tracks), ECL_BATCH_SIZE):
        batch = tracks[batch_start:batch_start + ECL_BATCH_SIZE]
        results = analyze_edge_case_batch(groq_client, batch, casing_for_analysis, {}, artist_track_names)
        for track, result in zip(batch, results):
            analyses[track["uri"]] = result
        if batch_start + ECL_BATCH_SIZE < len(tracks):
            time.sleep(2.5)

    logger.info("Local Edge Case Lab loaded %d tracks.", len(tracks))
    return {
        "tracks":        tracks,
        "analyses":      analyses,
        "review_folder": review_folder,
        "existing":      existing,
        "casing":        casing,
        "base_path":     folder_path,
    }


# ---------------------------------------------------------------------------
# LOCAL FILES — 5.7  Execute a single move from the Review folder
# ---------------------------------------------------------------------------
def execute_local_move(
    track_path: str,
    target_name: str,
    base_path: str,
    existing: dict,
    casing: dict,
) -> tuple[bool, str, bool]:
    """Move a file from the Review folder to a named destination subfolder.

    Args:
        track_path: Absolute path to the file to move.
        target_name: Display name of the destination subfolder.
        base_path: Root folder for subfolder creation.
        existing: {name_lower: path} — mutated in-place on creation.
        casing: {name_lower: display_name} — mutated in-place on creation.

    Returns:
        Tuple of (success, dest_display_name, created_new).
    """
    try:
        normalized = target_name.strip().lower()
        created_new = normalized not in existing

        dest_folder = get_or_create_local_folder(
            base_path, target_name.strip(), existing, casing
        )
        dest_filename = os.path.basename(track_path)
        dest_filepath = os.path.join(dest_folder, dest_filename)

        if os.path.exists(dest_filepath):
            logger.warning("execute_local_move: destination already exists '%s' — skipping.", dest_filepath)
            return False, "", False
        shutil.move(track_path, dest_filepath)
        dest_display = casing.get(normalized, target_name.strip())
        logger.info(
            "Moved '%s' to '%s' (%s).",
            track_path, dest_display, "new" if created_new else "existing",
        )
        return True, dest_display, created_new
    except Exception as exc:
        logger.error("execute_local_move failed: %s", exc)
        return False, "", False
