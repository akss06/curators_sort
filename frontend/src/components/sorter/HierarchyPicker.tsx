import { useState } from 'react'

interface HierarchyPickerProps {
  priorities: string[]
  onChange: (priorities: string[]) => void
  activeCount?: number
}

const DESCS: Record<string, string> = {
  Activity: 'e.g. Workout, Study, Sleep',
  Vibe:     'e.g. Chill, Hype, Melancholy',
  Genre:    'e.g. Hip-Hop, City Pop, Folk',
  Artist:   'Sort by artist name — no AI',
  Album:    'Sort by album name — no AI',
}



export function HierarchyPicker({ priorities, onChange, activeCount }: HierarchyPickerProps) {
  const activeN = activeCount ?? priorities.length
  const [dragIdx, setDragIdx] = useState<number | null>(null)
  const [overIdx, setOverIdx] = useState<number | null>(null)

  const onDragStart = (i: number) => setDragIdx(i)
  const onDragOver  = (e: React.DragEvent, i: number) => { e.preventDefault(); setOverIdx(i) }
  const onDrop      = (i: number) => {
    if (dragIdx === null || dragIdx === i) { setDragIdx(null); setOverIdx(null); return }
    const next = [...priorities]
    const [moved] = next.splice(dragIdx, 1)
    next.splice(i, 0, moved)
    onChange(next)
    setDragIdx(null); setOverIdx(null)
  }
  const onDragEnd = () => { setDragIdx(null); setOverIdx(null) }

  return (
    <div>
      <div className="patchboard" aria-label="Routing priority">
        {priorities.map((item, i) => {
          const isActive = i < activeN
          const isStandby = i === activeN
          return (
            <div key={item}>
              {isStandby && (
                <div style={{
                  fontFamily: 'var(--mono)', fontSize: 9, letterSpacing: '0.15em',
                  color: 'var(--ink-mute)', textTransform: 'uppercase',
                  padding: '6px 2px 4px', borderTop: '1px dashed var(--rule)',
                  marginTop: 4,
                }}>
                  Standby — drag to activate
                </div>
              )}
              <div
                className={[
                  'patch-row',
                  isActive ? '' : 'patch-row-standby',
                  dragIdx === i ? 'dragging' : '',
                  overIdx === i && dragIdx !== i ? 'drag-over' : '',
                ].filter(Boolean).join(' ')}
                draggable
                onDragStart={() => onDragStart(i)}
                onDragOver={e => onDragOver(e, i)}
                onDrop={() => onDrop(i)}
                onDragEnd={onDragEnd}
              >
                <span className="patch-idx serif" style={isActive ? {} : { color: 'var(--ink-mute)' }}>
                  {isActive ? i + 1 : '—'}
                </span>
                <div>
                  <div className="patch-label" style={isActive ? {} : { color: 'var(--ink-mute)' }}>{item}</div>
                  <div className="patch-desc">{DESCS[item]}</div>
                </div>
                <div className="grip">
                  <span /><span /><span /><span />
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
