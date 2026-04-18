type AppMode = 'local' | 'spotify'

interface LandingPageProps {
  onSelect: (mode: AppMode) => void
}

export function LandingPage({ onSelect }: LandingPageProps) {
  const now = new Date()
  const issue = now.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })

  return (
    <div className="landing-page">

      <header className="landing-masthead">
        <div className="landing-vol">
          <span className="small-caps">Vol. III — Special Edition</span>
          <span className="mono" style={{ fontSize: 10, color: 'var(--ink-mute)' }}>{issue}</span>
        </div>
        <div className="landing-title">
          <h1>The Curator's <em>Sorter</em></h1>
          <p className="landing-sub">
            An AI-powered music librarian. Route your collection to its proper shelves.
          </p>
        </div>
      </header>

      <div className="landing-rule-block">
        <span className="small-caps">— Choose your edition —</span>
      </div>

      <div className="mode-grid">

        {/* LOCAL FILES */}
        <div className="mode-card mode-local">
          <div className="mode-card-badge badge-local">No account required</div>
          <div className="mode-card-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M3 7v13a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1V7"/>
              <path d="M1 7h22"/>
              <path d="M16 3l-4 4-4-4"/>
              <circle cx="12" cy="15" r="2"/>
              <path d="M12 13v-2"/>
            </svg>
          </div>
          <h2 className="mode-card-title">Local Files</h2>
          <p className="mode-card-desc">
            Sort MP3s, FLACs, and other local audio into organised subfolders.
            Files are moved on your own machine — no cloud, no accounts.
          </p>
          <ul className="mode-features">
            <li><span className="feat-check">✓</span> MP3, FLAC, M4A, OGG, WAV, OPUS</li>
            <li><span className="feat-check">✓</span> Files moved into labelled subfolders</li>
            <li><span className="feat-check">✓</span> M3U playlist generated per folder</li>
            <li><span className="feat-check">✓</span> Dry-run preview before committing</li>
            <li><span className="feat-warn">⚠</span> Groq API key required for AI classification</li>
          </ul>
          <button className="mode-cta mode-cta-local" onClick={() => onSelect('local')}>
            Open Local Sorter ▶
          </button>
        </div>

        <div className="mode-divider" />

        {/* SPOTIFY */}
        <div className="mode-card mode-spotify">
          <div className="mode-card-badge badge-spotify">Requires API credentials</div>
          <div className="mode-card-icon" style={{ color: 'var(--sig-red)' }}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
            </svg>
          </div>
          <h2 className="mode-card-title">Spotify Library</h2>
          <p className="mode-card-desc">
            Sort your Liked Songs directly into Spotify playlists using the same
            AI classification engine.
          </p>
          <ul className="mode-features">
            <li><span className="feat-check">✓</span> Sorts Liked Songs into playlists</li>
            <li><span className="feat-check">✓</span> Edge Case Lab for ambiguous tracks</li>
            <li><span className="feat-check">✓</span> Run history with receipt cards</li>
            <li><span className="feat-check">✓</span> Dry-run preview before committing</li>
          </ul>

          <div className="mode-warning">
            <div className="mode-warning-head">⚠ Credentials required in <code>.env</code></div>
            <div className="mode-warning-rows">
              <div className="mode-warning-row">
                <span className="mono" style={{ fontSize: 10 }}>SPOTIFY_CLIENT_ID</span>
                <span className="mode-warning-src">Spotify Developer Dashboard</span>
              </div>
              <div className="mode-warning-row">
                <span className="mono" style={{ fontSize: 10 }}>SPOTIFY_CLIENT_SECRET</span>
                <span className="mode-warning-src">Spotify Developer Dashboard</span>
              </div>
              <div className="mode-warning-row">
                <span className="mono" style={{ fontSize: 10 }}>GROQ_API_KEY</span>
                <span className="mode-warning-src">console.groq.com</span>
              </div>
            </div>
            <p className="mode-warning-note">
              Spotify quota extension is restricted to organisations (250k MAU minimum).
              For personal use, up to 25 accounts can be allowlisted in Development Mode.
            </p>
          </div>

          <button className="mode-cta mode-cta-spotify" onClick={() => onSelect('spotify')}>
            Connect Spotify ▶
          </button>
        </div>

      </div>

      <footer className="landing-footer">
        <span className="mono" style={{ fontSize: 10, color: 'var(--ink-mute)' }}>
          Both modes require <code>GROQ_API_KEY</code> — classification is powered by <strong>llama-3.3-70b</strong> via Groq.
        </span>
      </footer>
    </div>
  )
}
