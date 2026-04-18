import { useState, useEffect, useCallback } from 'react'
import { createPortal } from 'react-dom'
import { FolderOpen, ArrowLeft, Check, Loader2 } from 'lucide-react'
import type { BrowseResponse } from '../../types'

interface FolderBrowserProps {
  selectedPath: string
  onSelect: (path: string) => void
}

export function FolderBrowser({ selectedPath, onSelect }: FolderBrowserProps) {
  const [open, setOpen] = useState(false)
  const [browsing, setBrowsing] = useState<BrowseResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const navigate = useCallback(async (path?: string) => {
    setLoading(true)
    setError(null)
    try {
      const url = path
        ? `/api/local/browse?path=${encodeURIComponent(path)}`
        : '/api/local/browse'
      const res = await fetch(url)
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || res.statusText)
      }
      setBrowsing(await res.json())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to browse')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (open && !browsing) navigate()
  }, [open, browsing, navigate])

  const handleOpen = () => {
    setOpen(true)
    if (!browsing) navigate()
  }

  const handleSelect = () => {
    if (browsing) {
      onSelect(browsing.current)
      setOpen(false)
    }
  }

  const handleClose = () => setOpen(false)

  const truncatePath = (p: string) => {
    const parts = p.replace(/\\/g, '/').split('/')
    if (parts.length <= 3) return p
    return '…/' + parts.slice(-2).join('/')
  }

  return (
    <>
      <div className="folder-picker">
        <div className="folder-picker-label">
          <span className="small-caps">Source folder</span>
          {selectedPath && (
            <span className="mono" style={{ fontSize: 10, color: 'var(--ink-mute)', wordBreak: 'break-all' }}>
              {truncatePath(selectedPath)}
            </span>
          )}
        </div>
        <button className="btn-secondary" onClick={handleOpen}>
          <FolderOpen size={12} />
          {selectedPath ? 'Change folder' : 'Choose folder'}
        </button>
      </div>

      {open && createPortal(
        <div className="modal-backdrop" onClick={handleClose}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <div className="modal-head">
              <div>
                <div className="serif" style={{ fontWeight: 600 }}>File Cabinet</div>
                <div className="small-caps" style={{ marginTop: 2 }}>choose a music folder</div>
              </div>
              <button className="btn-ghost" onClick={handleClose}>✕</button>
            </div>

            {browsing && (
              <div className="modal-crumb">
                {browsing.parent && (
                  <button className="crumb-back" onClick={() => navigate(browsing.parent!)}>
                    <ArrowLeft size={11} />
                  </button>
                )}
                <span className="mono" style={{ fontSize: 10, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {browsing.current}
                </span>
                {browsing.audio_count > 0 && (
                  <span className="tag tag-existing">{browsing.audio_count} tracks</span>
                )}
              </div>
            )}

            <div className="modal-body">
              {loading && (
                <div style={{ display: 'flex', justifyContent: 'center', padding: 24 }}>
                  <Loader2 size={16} style={{ animation: 'spin 1s linear infinite', color: 'var(--ink-mute)' }} />
                </div>
              )}

              {error && (
                <div className="error-bar" style={{ margin: '0 0 8px' }}>{error}</div>
              )}

              {!loading && browsing && browsing.audio_count === 0 && browsing.dirs.some(d => d.audio_count > 0) && (
                <div style={{
                  background: 'color-mix(in oklch, var(--sig-amber) 12%, transparent)',
                  border: '1px solid color-mix(in oklch, var(--sig-amber) 35%, transparent)',
                  borderRadius: 4,
                  padding: '8px 10px',
                  marginBottom: 8,
                  fontSize: 11,
                  fontFamily: 'var(--mono)',
                  color: 'var(--sig-amber)',
                  lineHeight: 1.5,
                }}>
                  ⚠ No audio files directly in this folder. The sorter only reads files in the root — navigate <em>into</em> the subfolder that contains your tracks.
                </div>
              )}

              {!loading && browsing && (
                browsing.dirs.length === 0 ? (
                  <div style={{ padding: '16px 0', color: 'var(--ink-mute)', fontSize: 12, fontFamily: 'var(--mono)' }}>
                    No subdirectories here.
                  </div>
                ) : (
                  <div className="dir-list">
                    {browsing.dirs.map(d => (
                      <button
                        key={d.path}
                        className="dir-row"
                        onClick={() => navigate(d.path)}
                      >
                        <FolderOpen size={12} style={{ opacity: 0.5, flexShrink: 0 }} />
                        <span style={{ flex: 1, textAlign: 'left', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {d.name}
                        </span>
                        {d.audio_count > 0 && (
                          <span className="mono" style={{ fontSize: 10, color: 'var(--ink-mute)', flexShrink: 0 }}>
                            {d.audio_count}
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                )
              )}
            </div>

            <div className="modal-foot">
              <button className="btn-ghost" onClick={handleClose}>Cancel</button>
              <button
                className="action-primary"
                onClick={handleSelect}
                disabled={!browsing || (browsing.audio_count === 0 && browsing.dirs.length === 0)}
              >
                <Check size={12} />
                <span>Select this folder</span>
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  )
}
