import type { LogEntry } from '../../types'

type Props = {
  logs: LogEntry[]
  isDryRun: boolean
}

const TAG_CLASS: Record<string, string> = {
  EXISTING: 'tag tag-existing',
  NEW:      'tag tag-new',
  REVIEW:   'tag tag-review',
  ERROR:    'tag tag-error',
}

const DEST_LABEL: Record<string, string> = {
  EXISTING: 'Existing',
  NEW:      'Created New',
  REVIEW:   'Held',
  ERROR:    'Error',
}

export function SorterResults({ logs, isDryRun }: Props) {
  return (
    <div className="ledger">
      <div className="ledger-head">
        <div>
          <div className="serif">The Placement Ledger</div>
          <div className="small-caps">
            {logs.length} rows · {isDryRun ? 'preview — no writes' : 'committed to Spotify'}
          </div>
        </div>
      </div>

      <div className="ledger-row head">
        <span>#</span>
        <span>Track</span>
        <span>Class.</span>
        <span>Destination</span>
        <span style={{ textAlign: 'right' }}>Status</span>
      </div>

      <div className="soft-scroll" style={{ maxHeight: 420, overflowY: 'auto' }}>
        {logs.map((L, i) => (
          <div key={i} className="ledger-row">
            <span className="ledger-num">{String(i + 1).padStart(2, '0')}</span>
            <div className="track-cell">
              <div className="t">{L.track}</div>
              <div className="a">{L.artist}</div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
              <span style={{ fontSize: 12 }}>
                {L.genre} · <i style={{ color: 'var(--ink-mute)' }}>{L.vibe}</i>
              </span>
              <div className="conf-bar">
                <div className="bar">
                  <i style={{ width: `${L.confidence}%` }} />
                </div>
                <span>{L.confidence}%</span>
              </div>
            </div>
            <div className="dest-cell">
              {L.destination}
              <small>{DEST_LABEL[L.resolution] ?? L.resolution}</small>
            </div>
            <span style={{ textAlign: 'right' }}>
              <span className={TAG_CLASS[L.resolution] ?? 'tag'}>{L.resolution}</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
