import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { TopNav, type TabKey } from './components/TopNav'
import { SorterTab } from './components/sorter/SorterTab'
import { ReviewTab } from './components/review/ReviewTab'
import { PlaylistsTab } from './components/playlists/PlaylistsTab'
import { LocalFilesTab } from './components/local/LocalFilesTab'
import { LandingPage } from './components/LandingPage'

type AppMode = 'unset' | 'local' | 'spotify'

interface AuthUser {
  display_name?: string | null
  user_id?: string | null
}

type AuthState = 'checking' | 'authenticated' | 'unauthenticated'

const MODE_KEY = 'app-mode'

export default function App() {
  const [appMode, setAppMode] = useState<AppMode>('unset')
  const [tab, setTab] = useState<TabKey>('sorter')
  const [authUser, setAuthUser] = useState<AuthUser | null>(null)
  const [authState, setAuthState] = useState<AuthState>('checking')
  const [loginLoading, setLoginLoading] = useState(false)

  // Only check Spotify auth when in spotify mode
  useEffect(() => {
    if (appMode !== 'spotify') return
    fetch('/api/auth/status')
      .then(r => r.json())
      .then(d => {
        if (d.authenticated) {
          setAuthUser(d)
          setAuthState('authenticated')
        } else {
          setAuthState('unauthenticated')
        }
      })
      .catch(() => setAuthState('unauthenticated'))
  }, [appMode])

  const handleModeSelect = (mode: 'local' | 'spotify') => {
    localStorage.setItem(MODE_KEY, mode)
    setAppMode(mode)
    if (mode === 'local') setTab('local')
    else setTab('sorter')
  }

  const handleGoHome = () => {
    localStorage.removeItem(MODE_KEY)
    setAppMode('unset')
    setAuthState('checking')
    setAuthUser(null)
  }

  const handleLogin = async () => {
    setLoginLoading(true)
    try {
      const res = await fetch('/api/oauth/login')
      const { auth_url } = await res.json()
      window.location.href = auth_url
    } catch {
      setLoginLoading(false)
    }
  }

  // — Landing page —
  if (appMode === 'unset') {
    return <LandingPage onSelect={handleModeSelect} />
  }

  // — Local Files mode: no auth required —
  if (appMode === 'local') {
    return (
      <div style={{ minHeight: '100vh', background: 'var(--paper)' }}>
        <header className="masthead">
          <div className="brand">
            <div>
              <div className="small-caps">Vol. III — The</div>
              <div className="brand-title">Curator's <em>Sorter</em></div>
            </div>
            <div className="brand-meta">
              <span className="small-caps" style={{ color: 'var(--good)' }}>Local Files Edition</span>
            </div>
          </div>
          <nav aria-label="Main navigation">
            <span className="nav-tab" aria-current="page">Local Files</span>
          </nav>
          <button className="btn-ghost" style={{ fontSize: 11 }} onClick={handleGoHome}>
            ← Change mode
          </button>
        </header>
        <div className="shell">
          <LocalFilesTab />
        </div>
      </div>
    )
  }

  // — Spotify mode —
  if (authState === 'checking') {
    return (
      <div className="login-wrap">
        <Loader2 style={{ width: 20, height: 20, animation: 'spin 1s linear infinite', color: 'var(--ink-mute)' }} />
      </div>
    )
  }

  if (authState === 'unauthenticated') {
    return (
      <div className="login-wrap">
        <div className="login-card">
          <div className="small-caps">— Vol. III · The —</div>
          <h1>Curator's <em>Sorter</em></h1>
          <p>
            A listening console for the exhausted. Connect your Spotify library and let
            the newsroom file your latest saves to their proper shelves.
          </p>
          <button className="login-btn" onClick={handleLogin} disabled={loginLoading}>
            {loginLoading
              ? <Loader2 style={{ width: 16, height: 16, animation: 'spin 1s linear infinite' }} />
              : <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/>
                </svg>
            }
            Connect Spotify ▶
          </button>
          <button className="btn-ghost" style={{ marginTop: 12, width: '100%', justifyContent: 'center' }} onClick={handleGoHome}>
            ← Back to mode selection
          </button>
        </div>
      </div>
    )
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--paper)' }}>
      <TopNav active={tab} onChange={setTab} userName={authUser?.display_name || 'User'} onGoHome={handleGoHome} />
      <div className="shell">
        {tab === 'sorter'    && <SorterTab />}
        {tab === 'review'    && <ReviewTab />}
        {tab === 'playlists' && <PlaylistsTab />}
        {tab === 'local'     && <LocalFilesTab />}
      </div>
    </div>
  )
}
