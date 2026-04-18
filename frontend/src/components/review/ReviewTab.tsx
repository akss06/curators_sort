import { useEffect } from 'react'
import { useReviewLab } from '../../hooks/useReviewLab'
import { TrackCard } from './TrackCard'

export function ReviewTab() {
  const { status, data, error, load, resolve, keepInReview } = useReviewLab()

  useEffect(() => { load() }, [load])

  return (
    <div>
      <div className="issue-line">
        <div className="serif" style={{ fontWeight: 500 }}>Edge Case Lab</div>
        <div className="kicker">Held tracks · human judgment</div>
      </div>

      <div className="panel" style={{ marginBottom: 20 }}>
        <div className="ecl-intro">
          <div>
            <div className="small-caps">The Curator's Desk</div>
            <h2 className="panel-title" style={{ fontStyle: 'italic' }}>These did not clear the cutoff.</h2>
            <p className="panel-sub" style={{ maxWidth: 620 }}>
              Each track was analyzed against your existing sonic profiles and flagged as ambiguous.
              Move to an existing playlist, coin a new one, or dismiss to review later.
            </p>
          </div>
        </div>
      </div>

      {status === 'loading' && (
        <div className="idle">
          <div className="kicker">Analyzing…</div>
          <h3>Loading <em>edge cases</em> from the archive.</h3>
        </div>
      )}

      {status === 'error' && (
        <div className="error-bar">
          {error === 'Failed to load review lab'
            ? 'Could not connect to backend. Make sure it is running.'
            : error}
        </div>
      )}

      {status === 'loaded' && data && data.tracks.length === 0 && (
        <div className="idle">
          <div className="kicker">end of file</div>
          <h3>The queue is <em>empty</em>. Nothing left to judge.</h3>
          <p>Run the sorter again and new edge cases will collect here.</p>
        </div>
      )}

      {status === 'loaded' && data && data.tracks.length > 0 && (
        <div className="ecl-grid">
          {data.tracks.map((track, i) => {
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
                onResolve={(targetPlaylist) => resolve(track.uri, targetPlaylist)}
                onKeep={() => keepInReview(track.uri)}
              />
            )
          })}
        </div>
      )}
    </div>
  )
}
