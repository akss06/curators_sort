interface LocalSorterControlsProps {
  limit: number
  setLimit: (v: number) => void
  allowNewFolders: boolean
  setAllowNewFolders: (v: boolean) => void
  dryRun: boolean
  setDryRun: (v: boolean) => void
  confidenceThreshold: number
  setConfidenceThreshold: (v: number) => void
  onRun: () => void
  disabled: boolean
  running: boolean
}

function SliderField({
  label, value, display, min, max, step, onChange, hint, ticks,
}: {
  label: string; value: number; display: string
  min: number; max: number; step: number
  onChange: (v: number) => void; hint?: string; ticks?: string[]
}) {
  return (
    <div className="field">
      <div className="field-head">
        <span className="field-label">{label}</span>
        <span className="field-value">{display}</span>
      </div>
      <input
        type="range" className="dial"
        min={min} max={max} step={step} value={value}
        onChange={e => onChange(Number(e.target.value))}
      />
      {ticks && (
        <div className="tick-row">
          {ticks.map(t => <span key={t}>{t}</span>)}
        </div>
      )}
      {hint && <div className="field-hint">{hint}</div>}
    </div>
  )
}

function ToggleRow({ label, hint, checked, onChange }: {
  label: string; hint?: string; checked: boolean; onChange: (v: boolean) => void
}) {
  return (
    <label className="toggle-row">
      <span
        className={`toggle-switch ${checked ? 'on' : ''}`}
        onClick={() => onChange(!checked)}
        role="switch"
        aria-checked={checked}
      />
      <input type="checkbox" className="sr-only" checked={checked} onChange={() => {}} />
      <span className="toggle-text">
        {label}
        {hint && <small>{hint}</small>}
      </span>
    </label>
  )
}

export function LocalSorterControls({
  limit, setLimit,
  allowNewFolders, setAllowNewFolders,
  dryRun, setDryRun,
  confidenceThreshold, setConfidenceThreshold,
  onRun, disabled, running,
}: LocalSorterControlsProps) {
  return (
    <div>
      <SliderField
        label="Files this run"
        value={limit}
        display={`${limit} pcs.`}
        min={10} max={500} step={10}
        ticks={['10', '100', '200', '350', '500']}
        onChange={setLimit}
      />
      <SliderField
        label="Hold threshold"
        value={confidenceThreshold}
        display={`≥ ${confidenceThreshold}%`}
        min={50} max={99} step={1}
        hint="Below this score, files go to the Review folder."
        onChange={setConfidenceThreshold}
      />

      <div style={{ marginTop: 6 }}>
        <ToggleRow
          label="Permit new folders"
          hint="Disable to force files into existing folders."
          checked={allowNewFolders}
          onChange={setAllowNewFolders}
        />
        <ToggleRow
          label="Dry run — preview only"
          hint="Classify without moving any files."
          checked={dryRun}
          onChange={setDryRun}
        />
      </div>

      <button
        className={`run-btn ${dryRun ? 'preview' : ''}`}
        disabled={disabled || running}
        onClick={onRun}
      >
        <span>
          {running
            ? (dryRun ? 'Previewing…' : 'Sorting…')
            : (dryRun ? 'Preview Run' : 'Run the Sorter')}
        </span>
        <span className="chev">▶▶</span>
      </button>

    </div>
  )
}
