# Curator's Sort

A full-stack web application that classifies your Spotify Liked Songs using AI and automatically sorts them into playlists based on a custom priority hierarchy (Activity, Vibe, Genre). Tracks are removed from Liked Songs after sorting so each run only processes new saves.

Also supports **Local Files** mode — sort your music folder using AI or metadata (Artist / Album) without any Spotify account.

---

## Architecture
- **Frontend**: React 19 + TypeScript (Vite)
- **Backend**: FastAPI (Python 3.10+)
- **AI Engine**: Groq (Llama 3.3 70B)

---

## Prerequisites

- Python 3.10+
- Node.js 18+
- A [Spotify Developer App](https://developer.spotify.com/dashboard) (for Spotify mode)
- A [Groq API key](https://console.groq.com) (free tier is fine)

---

## Setup

### 1. Clone & configure credentials

```bash
cp .env.example .env
```

Edit `.env` and fill in your keys:

```env
SPOTIFY_CLIENT_ID=...
SPOTIFY_CLIENT_SECRET=...
SPOTIFY_REDIRECT_URI=http://localhost:8000/api/oauth/callback
GROQ_API_KEY=...
```

**Spotify app settings** — in your Spotify Developer Dashboard, add this exact Redirect URI:
```
http://localhost:8000/api/oauth/callback
```

Required OAuth scopes (set automatically on first login):
```
playlist-read-private playlist-modify-private playlist-modify-public
user-library-read user-library-modify
```

### 2. Backend

```bash
# From the project root (curators_sort/)
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

---

## How It Works

1. **Sonic Profiling** — the backend samples your existing playlists to build a taste profile, reducing misclassification.
2. **AI Classification** — Groq uses a strict JSON-enforced prompt to categorise each track against your Priority Hierarchy.
3. **Sorting & Cleanup** — tracks are added to matching (or newly created) playlists and cleared from Liked Songs. Low-confidence tracks go to a *Review / Misc* playlist for manual review in the Edge Case Lab.

---

## Local Files Mode

No Spotify account required. Point the app at a local music folder and sort files into subfolders by AI tags (Activity / Vibe / Genre) or by metadata (Artist / Album). Files in a `Review/` subfolder can be triaged in the Local Review Lab.

---

## Notes

- The backend must run from the **project root**, not from `backend/`, so that `.env` and `.cache` resolve correctly.
- `runs.jsonl` is append-only run history — it is gitignored and stays local.
- `.cache` holds your Spotify OAuth token — keep it out of version control (already in `.gitignore`).
