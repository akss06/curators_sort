import { Loader2 } from 'lucide-react'
import { usePlaylists } from '../../hooks/usePlaylists'
import type { PlaylistItem } from '../../types'

type Shape = 'sun' | 'lines' | 'grid' | 'disc' | 'wave' | 'bolt' | 'fog' | 'qmark'

const SHAPES: Shape[] = ['sun', 'lines', 'grid', 'disc', 'wave', 'bolt', 'fog', 'qmark']
const HUES  = [18, 210, 340, 0, 160, 45, 260, 30]

function PlaylistShape({ shape, hue }: { shape: Shape; hue: number }) {
  const color = `oklch(0.62 0.17 ${hue})`
  const dark  = `oklch(0.22 0.06 ${hue})`
  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
    >
      <rect width="100" height="100" fill={color} />
      {shape === 'sun' && <>
        <circle cx="70" cy="30" r="22" fill={dark} />
        {Array.from({ length: 12 }).map((_, i) => {
          const a = (i * 30) * Math.PI / 180
          return <line key={i} x1="70" y1="30" x2={70 + Math.cos(a) * 46} y2={30 + Math.sin(a) * 46} stroke={dark} strokeWidth="1.5" />
        })}
      </>}
      {shape === 'lines' && Array.from({ length: 10 }).map((_, i) => (
        <line key={i} x1="0" y1={10 + i * 10} x2="100" y2={10 + i * 10} stroke={dark} strokeWidth={i % 3 === 0 ? 2 : 0.8} />
      ))}
      {shape === 'grid' && <>
        {Array.from({ length: 8 }).map((_, i) => <line key={'h' + i} x1="0" y1={i * 12 + 6} x2="100" y2={i * 12 + 6} stroke={dark} strokeWidth="0.8" />)}
        {Array.from({ length: 8 }).map((_, i) => <line key={'v' + i} x1={i * 12 + 6} y1="0" x2={i * 12 + 6} y2="100" stroke={dark} strokeWidth="0.8" />)}
      </>}
      {shape === 'disc' && <>
        <circle cx="50" cy="50" r="36" fill="none" stroke={dark} strokeWidth="2" />
        <circle cx="50" cy="50" r="26" fill="none" stroke={dark} strokeWidth="0.6" />
        <circle cx="50" cy="50" r="16" fill="none" stroke={dark} strokeWidth="0.6" />
        <circle cx="50" cy="50" r="5"  fill={dark} />
      </>}
      {shape === 'wave' && <>
        <path d="M0,60 Q25,20 50,60 T100,60" stroke={dark} strokeWidth="2" fill="none" />
        <path d="M0,75 Q25,35 50,75 T100,75" stroke={dark} strokeWidth="1.2" fill="none" />
        <path d="M0,45 Q25,5 50,45 T100,45"  stroke={dark} strokeWidth="1.2" fill="none" />
      </>}
      {shape === 'bolt' && (
        <polygon points="55,10 30,55 50,55 40,90 72,40 52,40 62,10" fill={dark} />
      )}
      {shape === 'fog' && <>
        <ellipse cx="30" cy="50" rx="30" ry="12" fill={dark} opacity=".5" />
        <ellipse cx="70" cy="65" rx="30" ry="10" fill={dark} opacity=".5" />
        <ellipse cx="50" cy="35" rx="28" ry="8"  fill={dark} opacity=".4" />
      </>}
      {shape === 'qmark' && (
        <text x="50" y="72" textAnchor="middle" fontFamily="serif" fontSize="72" fontStyle="italic" fill={dark}>?</text>
      )}
    </svg>
  )
}

function PlaylistCard({ playlist, index }: { playlist: PlaylistItem; index: number }) {
  const shape = SHAPES[index % SHAPES.length]
  const hue   = HUES[index % HUES.length]

  return (
    <a
      href={playlist.external_url || '#'}
      target="_blank"
      rel="noopener noreferrer"
      className="pl-card"
    >
      <div className="pl-cover">
        <PlaylistShape shape={shape} hue={hue} />
        <div className="pl-title">{playlist.name}</div>
      </div>
      <div className="pl-footer">
        <span className="count">{playlist.track_count} tracks</span>
        <span className="open">OPEN ↗</span>
      </div>
    </a>
  )
}

export function PlaylistsTab() {
  const { playlists, loading, error } = usePlaylists()

  return (
    <div>
      <div className="issue-line">
        <div className="serif" style={{ fontWeight: 500 }}>The Archive</div>
        <div className="kicker">
          {playlists.length > 0
            ? `${playlists.length} playlists · all destinations`
            : 'All destinations · read-only'}
        </div>
      </div>

      <div className="panel">
        <div className="stamp">CATALOGUED</div>
        <h2 className="panel-title">Your shelves, as they stand.</h2>
        <p className="panel-sub">Every destination the sorter can file to. Covers generated from playlist DNA.</p>

        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '24px 0', color: 'var(--ink-mute)' }}>
            <Loader2 style={{ width: 16, height: 16, animation: 'spin 1s linear infinite' }} />
            <span style={{ fontSize: 13 }}>Loading playlists…</span>
          </div>
        )}

        {error && (
          <div className="error-bar">
            {error === 'Failed to load playlists'
              ? "Could not connect to backend. Make sure it's running."
              : error}
          </div>
        )}

        {!loading && !error && playlists.length === 0 && (
          <div className="idle" style={{ marginTop: 0 }}>
            <div className="kicker">empty shelves</div>
            <h3>No playlists <em>yet</em>.</h3>
            <p>Run the sorter to create them.</p>
          </div>
        )}

        {!loading && playlists.length > 0 && (
          <div className="playlists-grid">
            {playlists.map((p, i) => (
              <PlaylistCard key={p.id} playlist={p} index={i} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
