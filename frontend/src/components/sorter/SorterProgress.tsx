import type { SortProgress, LogEntry } from '../../types'

type Props = {
  progress: SortProgress | null
  logs: LogEntry[]
  running: boolean
}

export function SorterProgress({ progress, logs, running }: Props) {
  const current = progress?.current ?? 0
  const total   = progress?.total   ?? 0
  const track   = progress?.track   ?? (logs[logs.length - 1]?.track ?? '—')
  const pct     = total ? Math.round((current / total) * 100) : 0

  const tickerItems = logs.length > 0
    ? logs.slice(-8).map(l => `${l.track} · ${l.artist} → ${l.destination}`)
    : ['Warming up the reels', 'Loading sonic profiles', 'Connecting to Groq', 'llama-3.3-70b']
  const tickerDup = [...tickerItems, ...tickerItems]

  return (
    <>
      {/* Reel */}
      <div className={`reel ${running ? 'spinning' : ''}`}>
        <div className="reel-wheel" />
        <div className="reel-body">
          <div className="small-caps">Now classifying</div>
          <div className="reel-track">{track}</div>
          <div className="reel-sub">
            <span className="mono">EL. {String(Math.floor(current * 2.5)).padStart(3, '0')}s</span>
            <span className="small-caps" style={{ letterSpacing: '.15em' }}>Model · llama-3.3-70b</span>
          </div>
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${pct}%` }} />
          </div>
        </div>
        <div className="reel-counter">
          {String(current).padStart(2, '0')}
          <span style={{ color: 'var(--ink-mute)' }}>/{String(total).padStart(2, '0')}</span>
          <small>{pct}% COMPLETE</small>
        </div>
      </div>

      {/* Ticker tape */}
      <div className="ticker">
        <div className="ticker-strip">
          {tickerDup.map((x, i) => (
            <span key={i}><span className="tk-dot">◆</span> {x}</span>
          ))}
        </div>
      </div>
    </>
  )
}
