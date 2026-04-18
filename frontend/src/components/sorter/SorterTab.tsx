import { useState, useEffect, useRef, useTransition } from 'react'
import { HierarchyPicker } from './HierarchyPicker'
import { SorterControls } from './SorterControls'
import { SorterProgress } from './SorterProgress'
import { SorterResults } from './SorterResults'
import { RunsHistory } from './RunsHistory'
import { useSortStream } from '../../hooks/useSortStream'

export function SorterTab() {
  const [priorities, setPriorities] = useState(['Activity', 'Vibe', 'Genre'])
  const [limit, setLimit] = useState(50)
  const [removeFromLiked, setRemoveFromLiked] = useState(true)
  const [allowNewPlaylists, setAllowNewPlaylists] = useState(true)
  const [dryRun, setDryRun] = useState(false)
  const [confidenceThreshold, setConfidenceThreshold] = useState(85)
  const [runsRefreshKey, setRunsRefreshKey] = useState(0)
  const [, startTransition] = useTransition()

  const { status, progress, logs, error, startSort, reset } = useSortStream()

  const prevStatus = useRef(status)
  useEffect(() => {
    if (prevStatus.current === 'running' && status === 'complete') {
      startTransition(() => setRunsRefreshKey(k => k + 1))
    }
    prevStatus.current = status
  }, [status, startTransition])

  const hierarchyValid = new Set(priorities).size === 3
  const isRunning = status === 'running' || status === 'starting'
  const showConsole = isRunning || logs.length > 0

  const handleRun = () => {
    startSort({ priorities, limit, removeFromLiked, allowNewPlaylists, dryRun, confidenceThreshold })
  }

  return (
    <div>
      <div className="issue-line">
        <div className="serif" style={{ fontWeight: 500 }}>The Auto-Sorter</div>
        <div className="kicker">Front desk · file new intake</div>
      </div>

      <div className="sorter-grid">
        <aside>
          <div className="panel">
            <div className="stamp">CONFIG · 001</div>
            <h2 className="panel-title">Patch the Board</h2>
            <p className="panel-sub">Drag to reorder. The model evaluates signals top-down.</p>
            <HierarchyPicker priorities={priorities} onChange={setPriorities} />
          </div>
        </aside>

        <aside>
          <div className="panel">
            <div className="stamp">DIALS</div>
            <h2 className="panel-title">Calibration</h2>
            <p className="panel-sub">Set the volume and the cutoff for held tracks.</p>
            <SorterControls
              limit={limit}
              setLimit={setLimit}
              removeFromLiked={removeFromLiked}
              setRemoveFromLiked={setRemoveFromLiked}
              allowNewPlaylists={allowNewPlaylists}
              setAllowNewPlaylists={setAllowNewPlaylists}
              dryRun={dryRun}
              setDryRun={setDryRun}
              confidenceThreshold={confidenceThreshold}
              setConfidenceThreshold={setConfidenceThreshold}
              onRun={handleRun}
              disabled={!hierarchyValid}
              running={isRunning}
            />
          </div>
        </aside>

        <section>
          {status === 'idle' && (
            <div className="panel" style={{ padding: 0 }}>
              <div className="idle">
                <div className="kicker">An intermission</div>
                <h3>The console is <em>quiet</em>. Your liked songs await a sorting hand.</h3>
                <p>
                  Set your hierarchy to the left, calibrate the dials, and press the big red button.
                </p>
                <div style={{
                  marginTop: 14,
                  borderTop: '1px solid var(--rule)',
                  paddingTop: 12,
                  display: 'grid',
                  gridTemplateColumns: 'auto 1fr',
                  columnGap: 10,
                  rowGap: 7,
                  textAlign: 'left',
                  fontSize: 12,
                  fontFamily: 'var(--mono)',
                  lineHeight: 1.5,
                  color: 'var(--ink-mute)',
                }}>
                  <span style={{ color: 'var(--sig-red)', fontWeight: 700 }}>01</span>
                  <span>Like a track in Spotify → it appears in your next sort run.</span>
                  <span style={{ color: 'var(--sig-red)', fontWeight: 700 }}>02</span>
                  <span>AI classifies each track and moves it into the best-matching playlist.</span>
                  <span style={{ color: 'var(--sig-red)', fontWeight: 700 }}>03</span>
                  <span>Low-confidence tracks go to <strong style={{ color: 'var(--ink)' }}>Review / Misc</strong> (auto-created). Handle them in the Edge Case Lab.</span>
                </div>
              </div>
            </div>
          )}

          {status === 'error' && error && (
            <div className="error-bar">
              <span style={{ flex: 1 }}>{error}</span>
              <button className="btn-ghost" onClick={reset}>Dismiss</button>
            </div>
          )}

          {showConsole && (
            <SorterProgress progress={progress} logs={logs} running={isRunning} />
          )}

          {logs.length > 0 && (
            <SorterResults logs={logs} isDryRun={dryRun} />
          )}

          {(status === 'complete' || status === 'error') && (
            <div style={{ textAlign: 'right', marginTop: 12 }}>
              <button className="btn-ghost" onClick={reset}>Start new run</button>
            </div>
          )}

          <div className="panel" style={{ marginTop: 22 }}>
            <div className="stamp">ARCHIVE</div>
            <h2 className="panel-title">Past Runs</h2>
            <p className="panel-sub">Previous sorting sessions, in receipt form.</p>
            <RunsHistory refreshKey={runsRefreshKey} />
          </div>
        </section>
      </div>
    </div>
  )
}
