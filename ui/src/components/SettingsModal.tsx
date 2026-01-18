/**
 * Settings Modal
 * ==============
 *
 * Quick run configuration for the next start.
 *
 * Keep the modal lightweight (small monitors). Full settings live on the Settings page.
 */

import { useMemo, useState } from 'react'
import { X, Settings as SettingsIcon, SlidersHorizontal, ExternalLink, CalendarClock } from 'lucide-react'
import { useAgentSchedule, useScheduleAgent, useCancelAgentSchedule } from '../hooks/useProjects'

export interface RunSettings {
  mode: 'standard' | 'parallel'
  parallelCount: number
  parallelPreset: 'quality' | 'balanced' | 'economy' | 'cheap' | 'experimental' | 'custom'
}

interface SettingsModalProps {
  onClose: () => void
  projectName: string
  yoloEnabled: boolean
  settings: RunSettings
  onChange: (next: RunSettings) => void
  onOpenSettingsPage?: () => void
}

export function SettingsModal({
  onClose,
  projectName,
  yoloEnabled,
  settings,
  onChange,
  onOpenSettingsPage,
}: SettingsModalProps) {
  const canUseParallel = !yoloEnabled
  const scheduleQuery = useAgentSchedule(projectName)
  const scheduleAgent = useScheduleAgent(projectName)
  const cancelSchedule = useCancelAgentSchedule(projectName)
  const [scheduleMode, setScheduleMode] = useState<'in' | 'at'>('in')
  const [delayMinutes, setDelayMinutes] = useState(30)
  const [scheduleAt, setScheduleAt] = useState(() => formatLocalInput(addMinutes(new Date(), 30)))

  const modeOptions = useMemo(
    () => [
      { id: 'standard' as const, label: 'Standard', help: 'Single agent run.' },
      { id: 'parallel' as const, label: 'Parallel', help: 'Worktree + multiple agents.' },
    ],
    []
  )

  const schedule = scheduleQuery.data
  const schedulePending = scheduleAgent.isPending || cancelSchedule.isPending

  const currentRunAt = schedule?.run_at ? parseLocalISO(schedule.run_at) : null
  const formattedRunAt = currentRunAt ? currentRunAt.toLocaleString() : ''

  const handleSchedule = async () => {
    let runAt: Date | null = null
    if (scheduleMode === 'in') {
      runAt = addMinutes(new Date(), delayMinutes)
    } else {
      runAt = parseLocalInput(scheduleAt)
    }
    if (!runAt || Number.isNaN(runAt.getTime())) return

    const request = {
      run_at: toLocalISO(runAt),
      yolo_mode: yoloEnabled,
      parallel_mode: !yoloEnabled && settings.mode === 'parallel',
      parallel_count: settings.parallelCount,
      model_preset: settings.parallelPreset,
    }
    await scheduleAgent.mutateAsync(request)
  }

  return (
    <div className="neo-modal-backdrop" onClick={onClose}>
      <div
        className="neo-modal w-full max-w-5xl h-[100dvh] sm:h-auto sm:max-h-[90vh] overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b-3 border-[var(--color-neo-border)]">
          <div className="flex items-center gap-3">
            <SettingsIcon className="text-[var(--color-neo-accent)]" size={28} />
            <h2 className="font-display text-2xl font-bold uppercase">Settings</h2>
          </div>
          <div className="flex items-center gap-2">
            {onOpenSettingsPage && (
              <button
                onClick={onOpenSettingsPage}
                className="neo-btn neo-btn-secondary text-sm"
                title="Open the full Settings page"
              >
                <ExternalLink size={18} />
                <span className="hidden sm:inline">Open</span>
              </button>
            )}
            <button onClick={onClose} className="neo-btn neo-btn-ghost p-2" aria-label="Close">
              <X size={24} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-110px)]">
          <div className="neo-card p-4 bg-[var(--color-neo-bg)]">
            <div className="font-display font-bold uppercase mb-2">Applies next start</div>
            <div className="text-sm text-[var(--color-neo-text-secondary)]">
              Start/stop controls stay in the header. Use the Settings page for Models + Advanced.
            </div>
          </div>

          {/* Mode */}
          <div className="mt-6">
            <div className="font-display font-bold uppercase text-sm mb-2 flex items-center gap-2">
              <SlidersHorizontal size={18} />
              Run Mode
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {modeOptions.map((opt) => {
                const disabled = opt.id === 'parallel' && !canUseParallel
                const active = settings.mode === opt.id
                return (
                  <button
                    key={opt.id}
                    className={`neo-card p-4 text-left transition-all ${
                      active ? 'ring-4 ring-[var(--color-neo-accent)] translate-x-[-4px] translate-y-[-4px]' : ''
                    } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
                    disabled={disabled}
                    onClick={() => onChange({ ...settings, mode: opt.id })}
                    title={disabled ? 'Disable YOLO to enable parallel mode' : opt.help}
                  >
                    <div className="font-display font-bold uppercase">{opt.label}</div>
                    <div className="text-sm text-[var(--color-neo-text-secondary)] mt-1">{opt.help}</div>
                    {opt.id === 'parallel' && yoloEnabled && (
                      <div className="text-xs font-mono mt-2 text-[var(--color-neo-danger)]">
                        Disabled while YOLO is enabled
                      </div>
                    )}
                  </button>
                )
              })}
            </div>
          </div>

          {/* Parallel settings */}
          {settings.mode === 'parallel' && (
            <div className="neo-card p-4 mt-6">
              <div className="font-display font-bold uppercase text-sm mb-3">Parallel</div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Agents</div>
                  <select
                    value={settings.parallelCount}
                    onChange={(e) => onChange({ ...settings, parallelCount: Number(e.target.value) })}
                    className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-display w-full"
                  >
                    <option value={1}>1 agent</option>
                    <option value={2}>2 agents</option>
                    <option value={3}>3 agents</option>
                    <option value={4}>4 agents</option>
                    <option value={5}>5 agents</option>
                  </select>
                </div>
                <div>
                  <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Preset (from Models)</div>
                  <div className="neo-card p-3 bg-[var(--color-neo-bg)] flex items-center justify-between">
                    <span className="font-mono text-sm font-bold">{settings.parallelPreset}</span>
                    {onOpenSettingsPage && (
                      <button
                        className="neo-btn neo-btn-secondary text-sm py-2 px-3"
                        onClick={onOpenSettingsPage}
                        title="Change models/presets in the Settings page"
                      >
                        Open
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Schedule */}
          <div className="neo-card p-4 mt-6">
            <div className="font-display font-bold uppercase text-sm mb-3 flex items-center gap-2">
              <CalendarClock size={18} />
              Schedule Run
            </div>

            {schedule?.scheduled && (
              <div className="neo-card p-3 mb-4 bg-[var(--color-neo-bg)]">
                <div className="text-sm font-bold">Scheduled for</div>
                <div className="text-sm text-[var(--color-neo-text-secondary)]">{formattedRunAt}</div>
                <div className="text-xs text-[var(--color-neo-text-secondary)] mt-1">
                  Mode: {schedule.parallel_mode ? `${schedule.parallel_count}x ${schedule.model_preset}` : schedule.yolo_mode ? 'YOLO' : 'Standard'}
                </div>
                <button
                  className="neo-btn neo-btn-danger text-sm mt-3"
                  onClick={() => cancelSchedule.mutate()}
                  disabled={schedulePending}
                >
                  Cancel schedule
                </button>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="neo-card p-3">
                <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Mode</div>
                <div className="flex gap-2">
                  <button
                    className={`neo-btn text-sm ${scheduleMode === 'in' ? 'neo-btn-primary' : 'neo-btn-secondary'}`}
                    onClick={() => setScheduleMode('in')}
                  >
                    In minutes
                  </button>
                  <button
                    className={`neo-btn text-sm ${scheduleMode === 'at' ? 'neo-btn-primary' : 'neo-btn-secondary'}`}
                    onClick={() => setScheduleMode('at')}
                  >
                    At time
                  </button>
                </div>
              </div>

              {scheduleMode === 'in' ? (
                <div>
                  <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Delay (minutes)</div>
                  <input
                    type="number"
                    min={1}
                    value={delayMinutes}
                    onChange={(e) => setDelayMinutes(Math.max(1, Number(e.target.value)))}
                    className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-mono w-full"
                  />
                </div>
              ) : (
                <div>
                  <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-1">Run at</div>
                  <input
                    type="datetime-local"
                    value={scheduleAt}
                    onChange={(e) => setScheduleAt(e.target.value)}
                    className="neo-btn text-sm py-2 px-3 bg-white border-3 border-[var(--color-neo-border)] font-mono w-full"
                  />
                </div>
              )}
            </div>

            <div className="mt-3 flex items-center gap-2">
              <button
                className="neo-btn neo-btn-primary text-sm"
                onClick={handleSchedule}
                disabled={schedulePending}
              >
                Schedule
              </button>
              <div className="text-xs text-[var(--color-neo-text-secondary)]">
                Uses the current run settings above.
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function addMinutes(date: Date, minutes: number): Date {
  return new Date(date.getTime() + minutes * 60000)
}

function pad2(value: number): string {
  return String(value).padStart(2, '0')
}

function formatLocalInput(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}T${pad2(date.getHours())}:${pad2(date.getMinutes())}`
}

function toLocalISO(date: Date): string {
  return formatLocalInput(date)
}

function parseLocalInput(value: string): Date | null {
  if (!value) return null
  const [datePart, timePart] = value.split('T')
  if (!datePart || !timePart) return null
  const [year, month, day] = datePart.split('-').map(Number)
  const [hour, minute] = timePart.split(':').map(Number)
  if (!year || !month || !day) return null
  return new Date(year, month - 1, day, hour || 0, minute || 0, 0)
}

function parseLocalISO(value: string): Date | null {
  return parseLocalInput(value)
}
