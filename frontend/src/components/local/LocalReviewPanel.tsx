import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { TrackCard } from '../review/TrackCard'
import { useLocalReviewLab } from '../../hooks/useLocalReviewLab'
import type { LocalTrackInfo } from '../../types'

interface LocalReviewPanelProps {
  folderPath: string
}

// ── Album batch card ──────────────────────────────────────────────────────────
interface AlbumBatchCardProps {
  album: string
  tracks: LocalTrackInfo[]
  suggestedName: string
  onMoveAll: (uris: string[], folderName: string) => Promise<unknown>
}

function AlbumBatchCard({ album, tracks, suggestedName, onMoveAll }: AlbumBatchCardProps) {
  const [folderName, setFolderName] = useState(suggestedName)
  const [moving, setMoving] = useState(false)
  const [done, setDone] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  const handleMove = async () => {
    if (!folderName.trim()) return
    setMoving(true)
    setErr(null)
    try {
      await onMoveAll(tracks.map(t => t.uri), folderName.trim())
      setDone(true)
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Move failed')
    } finally {
      setMoving(false)
    }
  }

  if (done) return null

  return (
    <div className="track-card">
      {/* Stamp — reuses the .stamp class, rotated opposite direction */}
      <div className="stamp" style={{ transform: 'rotate(3deg)' }}>BATCH</div>

      <div className="track-card-top">
        {/* Cover proxy: shows track count instead of art */}
        <div className="track-cover" style={{
          background: 'var(--paper-2)',
          color: 'var(--sig-red)',
          fontSize: 22,
          fontFamily: 'var(--serif)',
          fontWeight: 500,
        }}>
          {tracks.length}
        </div>

        <div className="track-info">
          <p className="n">{album}</p>
          <div className="a">{tracks.length} files · batch move</div>
          <div className="track-tags">
            <span className="tag tag-review">Album group</span>
          </div>
        </div>
      </div>

      {/* Track list rendered in the "reasoning" slot */}
      <div className="track-reasoning" style={{ fontStyle: 'normal', fontFamily: 'var(--mono)', fontSize: 11, lineHeight: 1.9 }}>
        {tracks.map(t => (
          <div key={t.uri} style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {t.name}
            {t.artist !== 'Unknown' && (
              <span style={{ color: 'var(--ink-mute)', marginLeft: 6 }}>— {t.artist}</span>
            )}
          </div>
        ))}
      </div>

      <div className="track-actions">
        {err && <p style={{ fontSize: 11, color: 'var(--sig-red)', margin: 0 }}>{err}</p>}

        {moving ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--ink-mute)' }}>
            <Loader2 style={{ width: 12, height: 12, animation: 'spin 1s linear infinite' }} />
            Moving {tracks.length} files…
          </div>
        ) : (
          <div className="create-row">
            <input
              id={`batch-folder-${album}`}
              value={folderName}
              onChange={e => setFolderName(e.target.value)}
              placeholder="folder name…"
              onKeyDown={e => { if (e.key === 'Enter') handleMove() }}
            />
            <button
              className="btn-secondary"
              onClick={handleMove}
              disabled={!folderName.trim()}
            >
              Move all →
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main panel ────────────────────────────────────────────────────────────────
export function LocalReviewPanel({ folderPath }: LocalReviewPanelProps) {
  const { status, data, error, load, resolve, resolveBatch, keepInReview } = useLocalReviewLab()

  if (status === 'idle') {
    return (
      <div className="panel">
        <div className="idle">
          <div className="kicker">Local review queue</div>
          <h3>Load files from the <em>Review</em> folder.</h3>
          <p>
            Tracks that scored below your confidence threshold live here.
            Run analysis to get placement suggestions.
          </p>
          <button className="action-primary" onClick={() => load(folderPath)} disabled={!folderPath}>
            <span>Load Review Folder</span>
          </button>
          {!folderPath && (
            <p style={{ fontSize: 11, color: 'var(--sig-red)', marginTop: 8 }}>
              Choose a source folder first.
            </p>
          )}
        </div>
      </div>
    )
  }

  if (status === 'loading') {
    return (
      <div className="panel">
        <div className="idle">
          <Loader2 style={{ width: 20, height: 20, animation: 'spin 1s linear infinite', color: 'var(--ink-mute)' }} />
          <p style={{ marginTop: 12, color: 'var(--ink-mute)', fontSize: 13 }}>
            Analysing Review folder with Groq…
          </p>
        </div>
      </div>
    )
  }

  if (status === 'error') {
    return (
      <div className="panel">
        <div className="error-bar">{error}</div>
        <button className="btn-ghost" style={{ marginTop: 8 }} onClick={() => load(folderPath)}>
          Retry
        </button>
      </div>
    )
  }

  if (!data || data.tracks.length === 0) {
    return (
      <div className="panel">
        <div className="idle">
          <div className="kicker">All clear</div>
          <h3>The Review folder is <em>empty</em>.</h3>
          <p>Run the auto-sorter first to populate it.</p>
          <button className="btn-ghost" onClick={() => load(folderPath)}>Reload</button>
        </div>
      </div>
    )
  }

  // ── Group tracks by album ──────────────────────────────────────────────────
  // Albums with 2+ tracks get a batch card; singleton tracks get individual cards.
  const albumGroups = new Map<string, LocalTrackInfo[]>()
  for (const track of data.tracks) {
    const key = track.album || 'Unknown'
    if (!albumGroups.has(key)) albumGroups.set(key, [])
    albumGroups.get(key)!.push(track)
  }

  const batchAlbums = [...albumGroups.entries()].filter(([, tracks]) => tracks.length >= 2)
  const batchUriSet = new Set(batchAlbums.flatMap(([, tracks]) => tracks.map(t => t.uri)))
  const soloTracks  = data.tracks.filter(t => !batchUriSet.has(t.uri))

  // Suggested folder name: album name if meaningful, else AI suggestion of first track
  const batchSuggestion = (album: string, tracks: LocalTrackInfo[]) => {
    if (album && album !== 'Unknown') return album
    const first = data.analyses[tracks[0].uri]
    return first?.suggested_new || 'Unsorted'
  }

  return (
    <div>
      <div className="issue-line">
        <div className="serif" style={{ fontWeight: 500 }}>Local Review Lab</div>
        <div className="kicker">{data.tracks.length} files awaiting placement</div>
      </div>

      <div className="ecl-grid">
        {/* Album batch cards */}
        {batchAlbums.map(([album, tracks]) => (
          <AlbumBatchCard
            key={album}
            album={album}
            tracks={tracks}
            suggestedName={batchSuggestion(album, tracks)}
            onMoveAll={(uris, folderName) => resolveBatch(uris, folderName)}
          />
        ))}

        {/* Individual track cards for albums with only one track */}
        {soloTracks.map((track, i) => {
          const analysis = data.analyses[track.uri]
          return (
            <TrackCard
              key={track.uri}
              name={track.name}
              artist={track.artist}
              reasoning={analysis?.reasoning}
              suggestedExisting={analysis?.suggested_existing}
              suggestedNew={analysis?.suggested_new}
              colorIndex={i}
              onResolve={target => resolve(track.uri, target)}
              onKeep={() => keepInReview(track.uri)}
            />
          )
        })}
      </div>
    </div>
  )
}
