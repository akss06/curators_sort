# Curator's Sort

A full-stack web application that classifies your Spotify Liked Songs using AI and automatically sorts them into playlists based on a custom priority hierarchy (Activity, Vibe, Genre). Tracks are removed from Liked Songs after sorting so each run only processes new saves.

---

## Architecture
- **Frontend**: React (Vite)
- **Backend**: FastAPI (Python)
- **AI Engine**: Groq (Llama 3.3 70B)


---

## Setup & Local Development

### 1. Backend (FastAPI)
Navigate to the root directory (`curators_sort/`).

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure credentials**
   Create a `.env` file in the root with your API keys:
   ```env
   SPOTIFY_CLIENT_ID=<your_client_id>
   SPOTIFY_CLIENT_SECRET=<your_client_secret>
   SPOTIFY_REDIRECT_URI=http://127.0.0.1:8000/callback
   GROQ_API_KEY=<your_groq_api_key>
   ```

3. **Run the Backend Server**
   ```bash
   uvicorn backend.main:app --reload --port 8000
   ```

### 2. Frontend (React)
Open a new terminal and navigate to the `frontend` directory.

1. **Install dependencies**
   ```bash
   cd frontend
   npm install
   ```

2. **Run the Development Server**
   ```bash
   npm run dev
   ```

---

## How It Works

1. **Sonic Profiling:** The backend dynamically pulls small samples of your existing playlists to inform the AI of your exact musical taste and prevent misclassification.
2. **AI Classification:** Groq uses a highly strict JSON-enforced prompt to categorize tracks based on your Priority Hierarchy.
3. **Sorting & Cleanup:** Tracks are added to matching (or newly created) playlists and then cleared from your Liked Songs. Any tracks with low confidence are safely routed to a "Review / Misc" playlist.
