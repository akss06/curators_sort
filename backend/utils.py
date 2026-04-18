import logging
from pathlib import Path

from fastapi import HTTPException

logger = logging.getLogger(__name__)


def validate_local_path(path: str) -> Path:
    """Resolve path and reject anything outside the user's home directory."""
    try:
        resolved = Path(path).resolve()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not resolved.is_relative_to(Path.home()):
        raise HTTPException(status_code=400, detail="Path must be within your home directory")
    return resolved


def validate_folder_name(name: str) -> None:
    """Reject folder names that contain path separators or traversal sequences."""
    if ".." in name or "/" in name or "\\" in name:
        raise HTTPException(status_code=400, detail="Invalid folder name")
