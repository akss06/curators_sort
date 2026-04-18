export type TabKey = 'sorter' | 'review' | 'playlists' | 'local'

type Props = {
  active: TabKey
  onChange: (tab: TabKey) => void
  userName: string
  onGoHome?: () => void
}

const tabs: Array<{ key: TabKey; label: string }> = [
  { key: 'sorter',    label: 'Auto-Sorter'   },
  { key: 'review',   label: 'Edge Case Lab'  },
  { key: 'playlists', label: 'Playlists'     },
]

export function TopNav({ active, onChange, userName, onGoHome }: Props) {
  const now = new Date()
  const issue = now.toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })
  const initials = userName.split(' ').map(n => n[0]).slice(0, 2).join('').toUpperCase()

  return (
    <header className="masthead">
      <div className="brand">
        <div>
          <div className="small-caps">Vol. III — The</div>
          <div className="brand-title">Curator's <em>Sorter</em></div>
        </div>
        <div className="brand-meta">
          <span className="small-caps">Issued</span>
          <span className="mono" style={{ fontSize: 11 }}>{issue}</span>
        </div>
      </div>

      <nav aria-label="Main navigation">
        {tabs.map(t => (
          <button
            key={t.key}
            className="nav-tab"
            aria-current={active === t.key ? 'page' : undefined}
            onClick={() => onChange(t.key)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {onGoHome && (
          <button className="btn-ghost" style={{ fontSize: 11 }} onClick={onGoHome}>
            ← Change mode
          </button>
        )}
        <div className="masthead-avatar" title={userName}>{initials}</div>
      </div>
    </header>
  )
}
