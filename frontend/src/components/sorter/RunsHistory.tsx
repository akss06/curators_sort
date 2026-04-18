import { useState, useEffect, useTransition } from 'react'
import type { RunEntry } from '../../types'

export function RunsHistory({ refreshKey = 0 }: { refreshKey?: number }) {
  const [open, setOpen] = useState(false)
  const [runs, setRuns] = useState<RunEntry[]>([])
  const [isPending, startTransition] = useTransition()

  useEffect(() => {
    if (!open) return
    startTransition(async () => {
      const d = await fetch('/api/runs?limit=20')
        .then(r => r.json())
        .catch(() => ({ runs: [] }))
      setRuns(d.runs || [])
    })
  }, [open, refreshKey, startTransition])

  const formatDate = (iso: string) => {
    const d = new Date(iso)
    return d.toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
  }

  return (
    <div>
      <button
        className="receipts-toggle"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
      >
        <span className={`chevron ${open ? 'open' : ''}`} style={{ fontFamily: 'var(--mono)' }}>▾</span>
        Past Runs
      </button>

      {open && (
        <div style={{ marginTop: 16, borderTop: '1px solid var(--rule)', paddingTop: 16 }}>
          {isPending && (
            <p style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-mute)' }}>Loading…</p>
          )}
          {!isPending && runs.length === 0 && (
            <p style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--ink-mute)' }}>
              No past runs yet.
            </p>
          )}
          {!isPending && runs.length > 0 && (
            <div className="receipts">
              {runs.map(run => (
                <div key={run.id} className="receipt">
                  <div className="receipt-head">
                    <div>
                      <div className="serif">
                        {run.priorities.join(' => ')}
                        {run.dry_run && (
                          <span className="mono" style={{ marginLeft: 8, fontSize: 10, color: 'var(--sig-red)' }}>
                            [PREVIEW]
                          </span>
                        )}
                      </div>
                      <div className="mono">{formatDate(run.timestamp)}</div>
                    </div>
                    <div className="mono" style={{ fontSize: 10, color: 'var(--ink-mute)' }}>
                      #{run.id.slice(0, 8).toUpperCase()}
                    </div>
                  </div>
                  <div className="receipt-stats">
                    <div><div className="n">{run.stats.sorted}</div><div className="l">Sorted</div></div>
                    <div><div className="n">{run.stats.review}</div><div className="l">Held</div></div>
                    <div><div className="n">{run.stats.new_playlists}</div><div className="l">New PL</div></div>
                    <div><div className="n">{run.stats.duplicates}</div><div className="l">Dupes</div></div>
                  </div>
                  {run.logs.length > 0 && (
                    <div className="receipt-sample">
                      {run.logs.slice(0, 3).map(l => l.track).join(' - ')}
                      {run.logs.length > 3 && ` +${run.logs.length - 3} more`}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
