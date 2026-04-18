"""
main.py
-------
FastAPI application entry point for The Exhausted Curator's Sorter.

Run from the project root (curators_sort/):
    uvicorn backend.main:app --reload --port 8000

IMPORTANT: Must be run from the project root so that engine.py resolves
.cache and .env relative to the working directory, not relative to backend/.
"""

import os
import sys

# Ensure the project root is on the path so `import engine` works
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

from backend.limiter import limiter
from backend.routes import auth, playlists, sort, review_lab, runs, oauth
from backend.routes import local_browse, local_sort, local_review_lab

_frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")

app = FastAPI(
    title="Curator's Sorter API",
    description="FastAPI backend for the Spotify Auto-Sorter",
    version="2.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[_frontend_url],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(auth.router)
app.include_router(playlists.router)
app.include_router(sort.router)
app.include_router(review_lab.router)
app.include_router(runs.router)
app.include_router(oauth.router)
app.include_router(local_browse.router)
app.include_router(local_sort.router)
app.include_router(local_review_lab.router)
