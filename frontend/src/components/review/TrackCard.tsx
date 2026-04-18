import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import type { ResolveResponse } from '../../types'

interface TrackCardProps {
  name: string
  artist: string
  reasoning?: string
  suggestedExisting?: string
  suggestedNew?: string
  colorIndex: number
  onResolve: (targetPlaylist: string) => Promise<ResolveResponse>
  onKeep: () => void
}

const CONIC_ANGLES = [0, 90, 45, 135, 20, 160, 70]

export function TrackCard({
  name, artist, reasoning, suggestedExisting, suggestedNew,
  colorIndex, onResolve, onKeep,
}: TrackCardProps) {
  const [resolving, setResolving] = useState(false)
  const [resolved, setResolved] = useState(false)
  const [newName, setNewName] = useState(suggestedNew ?? "")
  const [error, setError] = useState<string | null>(null)

  const hasExisting = suggestedExisting && suggestedExisting !== "NONE"
  const angle = CONIC_ANGLES[colorIndex % CONIC_ANGLES.length]
  const coverStyle = {
    background: `conic-gradient(from ${angle}deg, var(--sig-red), var(--ink), var(--amber), var(--ink))`,
  }

  const handleResolve = async (target: string) => {
    if (!target.trim()) return
    setResolving(true)
    setError(null)
    try {
      await onResolve(target.trim())
      setResolved(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to resolve")
      setResolving(false)
    }
  }

  return (
    <div className="track-card">
      {resolved && <div className="resolved-stamp">filed.</div>}

      <div className="track-card-top">
        <div className="track-cover" style={coverStyle}>
          {artist[0]}
        </div>
        <div className="track-info">
          <p className="n">{name}</p>
          <div className="a">
            {artist} · held <span style={{ color: "var(--sig-red)" }}>●</span>
          </div>
          <div className="track-tags">
            <span className="tag tag-review">Ambiguous</span>
            {!hasExisting && <span className="tag tag-new">No match</span>}
          </div>
        </div>
      </div>

      {reasoning && (
        <div className="track-reasoning">{reasoning}</div>
      )}

      <div className="track-actions">
        {error && (
          <p style={{ fontSize: 11, color: "var(--sig-red)", margin: 0 }}>{error}</p>
        )}

        {resolving ? (
          <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--ink-mute)" }}>
            <Loader2 style={{ width: 12, height: 12, animation: "spin 1s linear infinite" }} />
            Moving track…
          </div>
        ) : (
          <>
            {hasExisting && (
              <button
                className="action-primary"
                onClick={() => handleResolve(suggestedExisting!)}
              >
                <span>
                  Move to <span className="serif">{suggestedExisting}</span>
                </span>
                <span className="mono" style={{ fontSize: 10, opacity: 0.6 }}>ENTER</span>
              </button>
            )}

            <div className="create-row">
              <input
                value={newName}
                onChange={e => setNewName(e.target.value)}
                placeholder="new playlist name…"
              />
              <button
                className="btn-secondary"
                onClick={() => handleResolve(newName)}
                disabled={!newName.trim()}
              >
                + Coin &amp; Move
              </button>
            </div>

            <button className="btn-ghost" onClick={onKeep}>
              dismiss — decide later
            </button>
          </>
        )}
      </div>
    </div>
  )
}
