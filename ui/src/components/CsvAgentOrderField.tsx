/**
 * CSV Agent Order Field
 * =====================
 *
 * UI helper for ordered multi-select of Codex/Gemini agents with an optional raw CSV escape hatch.
 * Used anywhere we accept "codex,gemini" style ordering for multi_cli providers.
 */

import { ArrowDown, ArrowUp } from 'lucide-react'

type AgentId = 'codex' | 'gemini'

export function CsvAgentOrderField({
  label,
  value,
  onChange,
  error,
  warning,
  disabled,
  availability,
  rawPlaceholder,
  rawLabel,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  error?: string
  warning?: string
  disabled?: boolean
  availability?: { codex?: boolean; gemini?: boolean }
  rawPlaceholder?: string
  rawLabel?: string
}) {
  const normalize = (raw: string) =>
    raw
      .replace(/;/g, ',')
      .split(',')
      .map((p) => p.trim().toLowerCase())
      .filter(Boolean)

  const allowed = new Set(['codex', 'gemini'])
  const rawTokens = normalize(value)
  const selected = rawTokens.filter((t) => allowed.has(t)) as AgentId[]
  const uniqueSelected = Array.from(new Set(selected)) as AgentId[]

  const setSelected = (next: AgentId[]) => {
    onChange(next.join(','))
  }

  const canSelect = (id: AgentId) => {
    const avail = availability?.[id]
    return avail !== false
  }

  const toggle = (id: AgentId, nextChecked: boolean) => {
    if (disabled) return
    if (nextChecked) {
      if (!canSelect(id)) return
      if (uniqueSelected.includes(id)) return
      setSelected([...uniqueSelected, id])
      return
    }
    setSelected(uniqueSelected.filter((x) => x !== id))
  }

  const move = (id: AgentId, dir: -1 | 1) => {
    const idx = uniqueSelected.indexOf(id)
    if (idx < 0) return
    const nextIdx = idx + dir
    if (nextIdx < 0 || nextIdx >= uniqueSelected.length) return
    const next = [...uniqueSelected]
    const tmp = next[idx]
    next[idx] = next[nextIdx]
    next[nextIdx] = tmp
    setSelected(next)
  }

  const border =
    error ? 'border-[var(--color-neo-danger)]' : warning ? 'border-yellow-600' : 'border-[var(--color-neo-border)]'

  return (
    <div>
      <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">{label}</div>
      <div className={`neo-card p-3 border-3 ${border}`}>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {(['codex', 'gemini'] as const).map((id) => {
            const avail = availability?.[id]
            const checked = uniqueSelected.includes(id)
            const disabledCheck = Boolean(disabled) || (avail === false && !checked)
            const badge = avail === false ? 'Missing' : 'OK'
            return (
              <label key={id} className={`neo-card p-2 flex items-center justify-between ${disabledCheck ? 'opacity-60' : ''}`}>
                <span className="flex items-center gap-2">
                  <span className="font-display font-bold text-sm">{id === 'codex' ? 'Codex' : 'Gemini'}</span>
                  <span
                    className={`neo-badge text-xs font-mono ${
                      avail === false ? 'bg-[var(--color-neo-pending)] text-[var(--color-neo-text-on-bright)]' : 'bg-[var(--color-neo-bg)]'
                    }`}
                    title={avail === false ? 'CLI not detected on PATH' : 'CLI detected'}
                  >
                    {badge}
                  </span>
                </span>
                <input
                  type="checkbox"
                  checked={checked}
                  disabled={disabledCheck}
                  onChange={(e) => toggle(id, e.target.checked)}
                  className="w-5 h-5"
                />
              </label>
            )
          })}
        </div>

        {uniqueSelected.length > 1 && (
          <div className="mt-3">
            <div className="text-xs text-[var(--color-neo-text-secondary)] mb-1">Order (first tries first)</div>
            <div className="space-y-2">
              {uniqueSelected.map((id) => (
                <div key={id} className="flex items-center justify-between gap-2">
                  <span className="neo-badge font-mono">{id}</span>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className="neo-btn neo-btn-secondary neo-btn-sm"
                      onClick={() => move(id, -1)}
                      disabled={disabled || uniqueSelected.indexOf(id) === 0}
                      title="Move up"
                    >
                      <ArrowUp size={14} />
                    </button>
                    <button
                      type="button"
                      className="neo-btn neo-btn-secondary neo-btn-sm"
                      onClick={() => move(id, 1)}
                      disabled={disabled || uniqueSelected.indexOf(id) === uniqueSelected.length - 1}
                      title="Move down"
                    >
                      <ArrowDown size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <details className="mt-3">
          <summary className="text-xs font-mono cursor-pointer select-none text-[var(--color-neo-text-secondary)]">
            Advanced: raw CSV
          </summary>
          <div className="mt-2">
            <input
              type="text"
              value={value}
              onChange={(e) => onChange(e.target.value)}
              placeholder={rawPlaceholder ?? 'e.g. codex,gemini'}
              disabled={disabled}
              aria-label={rawLabel ?? `${label} raw CSV`}
              className={`neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-mono w-full ${
                disabled ? 'opacity-60 cursor-not-allowed' : ''
              }`}
            />
          </div>
        </details>
      </div>

      {error && <div className="text-xs mt-1 text-[var(--color-neo-danger)]">{error}</div>}
      {!error && warning && <div className="text-xs mt-1 text-yellow-800">{warning}</div>}
    </div>
  )
}

