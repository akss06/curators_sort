import { useState, useEffect, useTransition } from 'react'
import { FolderBrowser } from './FolderBrowser'
import { LocalSorterControls } from './LocalSorterControls'
import { LocalReviewPanel } from './LocalReviewPanel'
import { HierarchyPicker } from '../sorter/HierarchyPicker'
import { SorterProgress } from '../sorter/SorterProgress'
import { SorterResults } from '../sorter/SorterResults'
import { useLocalSortStream } from '../../hooks/useLocalSortStream'
import type { BrowseResponse } from '../../types'

type LocalSubTab = 'sort' | 'review'
type SortMode = 'ai' | 'metadata'


const FOLDER_KEY = 'local-folder-path'

export function LocalFilesTab() {
  const [subTab, setSubTab] = useState<LocalSubTab>('sort')
  const [sortMode, setSortMode] = useState<SortMode>('ai')
  const [folderPath, setFolderPath] = useState<string>(
    () => localStorage.getItem(FOLDER_KEY) || ''
  )
  const [priorities, setPriorities] = useState(['Activity', 'Vibe', 'Genre'])
  const [limit, setLimit] = useState(200)
  const [allowNewFolders, setAllowNewFolders] = useState(true)
  const [dryRun, setDryRun] = useState(false)
  const [confidenceThreshold, setConfidenceThreshold] = useState(85)
  const [folderInfo, setFolderInfo] = useState<BrowseResponse | null>(null)
  const [, startTransition] = useTransition()
  const { status, progress, logs, error, startSort, reset } = useLocalSortStream()

  useEffect(() => {
    startTransition(async () => {
      if (!folderPath) { setFolderInfo(null); return }
      try {
        const res = await fetch(`/api/local/browse?path=${encodeURIComponent(folderPath)}`)
        if (res.ok) setFolderInfo(await res.json())
        else setFolderInfo(null)
      } catch { setFolderInfo(null) }
    })
  }, [folderPath, startTransition])

  const handleFolderSelect = (path: string) => {
    setFolderPath(path)
    localStorage.setItem(FOLDER_KEY, path)
  }

  const handleModeChange = (mode: SortMode) => {
    setSortMode(mode)
    setPriorities(mode === 'ai' ? ['Activity', 'Vibe', 'Genre'] : ['Artist', 'Album'])
  }

  const hierarchyValid = sortMode === 'ai'
    ? new Set(priorities).size === 3
    : new Set(priorities).size === 2
  const folderHasNoDirectAudio = folderPath.trim().length > 0 && folderInfo !== null && folderInfo.audio_count === 0
  const canRun = hierarchyValid && folderPath.trim().length > 0 && !folderHasNoDirectAudio
  const isRunning = status === 'running' || status === 'starting'
  const showConsole = isRunning || logs.length > 0

  const handleRun = () => {
    startSort({ folderPath, priorities, limit, allowNewFolders, dryRun, confidenceThreshold })
  }

  return (
    <div>
      <div className="issue-line">
        <div className="serif" style={{ fontWeight: 500 }}>Local Files</div>
        <div className="kicker">Sort your local music library with AI</div>
      </div>

      <div className="local-subtabs">
        <button
          className={`nav-tab ${subTab === 'sort' ? 'active' : ''}`}
          aria-current={subTab === 'sort' ? 'page' : undefined}
          onClick={() => setSubTab('sort')}
        >
          Auto-Sort
        </button>
        <button
          className={`nav-tab ${subTab === 'review' ? 'active' : ''}`}
          aria-current={subTab === 'review' ? 'page' : undefined}
          onClick={() => setSubTab('review')}
        >
          Review Lab
        </button>
      </div>

      {subTab === 'sort' && (
        <div className="sorter-grid">
          <aside>
            <div className="panel">
              <div className="stamp">SOURCE</div>
              <h2 className="panel-title">Music Folder</h2>
              <p className="panel-sub">Files in the root of this folder will be sorted into subfolders.</p>
              <FolderBrowser selectedPath={folderPath} onSelect={handleFolderSelect} />
            </div>

            <div className="panel">
              <div className="stamp">CONFIG · 001</div>
              <h2 className="panel-title">Patch the Board</h2>
              <p className="panel-sub">
                {sortMode === 'ai'
                  ? 'Drag to reorder. The model evaluates signals top-down.'
                  : 'Files are sorted by metadata — no AI call.'}
              </p>

              {/* ── Sort-mode toggle ── */}
              <div style={{
                display: 'flex', gap: 6, marginBottom: 14,
                fontFamily: 'var(--mono)', fontSize: 11,
              }}>
                {(['ai', 'metadata'] as SortMode[]).map(mode => (
                  <button
                    key={mode}
                    id={`sort-mode-${mode}`}
                    onClick={() => handleModeChange(mode)}
                    style={{
                      flex: 1,
                      padding: '5px 0',
                      borderRadius: 4,
                      border: '1px solid',
                      cursor: 'pointer',
                      letterSpacing: '0.08em',
                      textTransform: 'uppercase',
                      fontSize: 10,
                      fontFamily: 'var(--mono)',
                      fontWeight: sortMode === mode ? 700 : 400,
                      background: sortMode === mode ? 'var(--ink)' : 'transparent',
                      color: sortMode === mode ? 'var(--paper)' : 'var(--ink-mute)',
                      borderColor: sortMode === mode ? 'var(--ink)' : 'var(--rule)',
                      transition: 'all 0.15s',
                    }}
                  >
                    {mode === 'ai' ? 'AI Sort' : 'Metadata Sort'}
                  </button>
                ))}
              </div>

              <HierarchyPicker priorities={priorities} onChange={setPriorities} />
            </div>
          </aside>

          <aside>
            <div className="panel">
              <div className="stamp">DIALS</div>
              <h2 className="panel-title">Calibration</h2>
              <p className="panel-sub">Set the volume and the cutoff for held files.</p>
              <LocalSorterControls
                limit={limit}
                setLimit={setLimit}
                allowNewFolders={allowNewFolders}
                setAllowNewFolders={setAllowNewFolders}
                dryRun={dryRun}
                setDryRun={setDryRun}
                confidenceThreshold={confidenceThreshold}
                setConfidenceThreshold={setConfidenceThreshold}
                onRun={handleRun}
                disabled={!canRun}
                running={isRunning}
              />
              {!folderPath && (
                <p style={{ fontSize: 11, color: 'var(--sig-red)', marginTop: 8, fontFamily: 'var(--mono)', textAlign: 'center' }}>
                  ↑ Choose a source folder to enable sorting
                </p>
              )}
              {folderHasNoDirectAudio && (
                <p style={{ fontSize: 11, color: 'var(--sig-amber)', marginTop: 8, fontFamily: 'var(--mono)', lineHeight: 1.5 }}>
                  ⚠ No audio files found directly in this folder. The sorter only reads files in the root — select the subfolder that contains your tracks.
                </p>
              )}
            </div>
          </aside>

          <section>
            {status === 'idle' && (
              <div className="panel" style={{ padding: 0 }}>
                <div className="idle">
                  <div className="kicker">An intermission</div>
                  <h3>Choose a folder and <em>run the sorter</em>.</h3>
                  <p>
                    Files in the root of your chosen folder will be classified and moved
                    into subfolders. An M3U playlist is generated for each destination.
                  </p>
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
          </section>
        </div>
      )}

      {subTab === 'review' && (
        <LocalReviewPanel folderPath={folderPath} />
      )}
    </div>
  )
}
