import { CheckCircle2, Circle, Clock, AlertCircle, XCircle } from 'lucide-react'
import type { PhaseData, PhaseStatus } from './PhaseCard'

interface PhaseTimelineProps {
  phases: PhaseData[]
  onPhaseClick?: (phase: PhaseData) => void
  currentPhaseId?: number
}

function getStatusIcon(status: PhaseStatus) {
  switch (status) {
    case 'completed':
      return <CheckCircle2 size={20} className="text-[var(--color-neo-done)]" />
    case 'in_progress':
      return <Clock size={20} className="text-[var(--color-neo-progress)]" />
    case 'awaiting_approval':
      return <AlertCircle size={20} className="text-amber-500" />
    case 'rejected':
      return <XCircle size={20} className="text-red-500" />
    case 'pending':
    default:
      return <Circle size={20} className="text-[var(--color-neo-text-secondary)]" />
  }
}

function getStatusColor(status: PhaseStatus): string {
  switch (status) {
    case 'completed':
      return 'var(--color-neo-done)'
    case 'in_progress':
      return 'var(--color-neo-progress)'
    case 'awaiting_approval':
      return '#f59e0b'
    case 'rejected':
      return '#ef4444'
    case 'pending':
    default:
      return 'var(--color-neo-border)'
  }
}

export function PhaseTimeline({
  phases,
  onPhaseClick,
  currentPhaseId,
}: PhaseTimelineProps) {
  if (phases.length === 0) {
    return (
      <div className="text-center text-[var(--color-neo-text-secondary)] py-8">
        No phases defined
      </div>
    )
  }

  return (
    <div className="relative">
      {/* Horizontal Timeline for larger screens */}
      <div className="hidden md:block">
        <div className="flex items-start justify-between">
          {phases.map((phase, index) => (
            <div
              key={phase.id}
              className="flex-1 relative"
            >
              {/* Connector line */}
              {index < phases.length - 1 && (
                <div
                  className="absolute top-4 left-1/2 w-full h-0.5"
                  style={{
                    backgroundColor:
                      phase.status === 'completed'
                        ? 'var(--color-neo-done)'
                        : 'var(--color-neo-border)',
                  }}
                />
              )}

              {/* Phase node */}
              <button
                onClick={() => onPhaseClick?.(phase)}
                className={`
                  relative z-10 flex flex-col items-center
                  ${onPhaseClick ? 'cursor-pointer group' : ''}
                `}
              >
                {/* Icon circle */}
                <div
                  className={`
                    w-8 h-8 rounded-full flex items-center justify-center
                    bg-[var(--color-neo-card)] border-2 transition-transform
                    ${currentPhaseId === phase.id ? 'scale-125 ring-2 ring-offset-2' : ''}
                    ${onPhaseClick ? 'group-hover:scale-110' : ''}
                  `}
                  style={{
                    borderColor: getStatusColor(phase.status),
                    ringColor: getStatusColor(phase.status),
                  }}
                >
                  {getStatusIcon(phase.status)}
                </div>

                {/* Phase info */}
                <div className="mt-2 text-center max-w-[120px]">
                  <div className="text-xs font-mono text-[var(--color-neo-text-secondary)]">
                    Phase {phase.order + 1}
                  </div>
                  <div className="font-bold text-sm line-clamp-2">
                    {phase.name}
                  </div>
                  <div className="text-xs text-[var(--color-neo-text-secondary)]">
                    {phase.percentage}% complete
                  </div>
                </div>
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Vertical Timeline for mobile */}
      <div className="md:hidden space-y-4">
        {phases.map((phase, index) => (
          <div key={phase.id} className="flex gap-3">
            {/* Left side: icon and connector */}
            <div className="flex flex-col items-center">
              {/* Icon */}
              <button
                onClick={() => onPhaseClick?.(phase)}
                className={`
                  w-8 h-8 rounded-full flex items-center justify-center
                  bg-[var(--color-neo-card)] border-2
                  ${currentPhaseId === phase.id ? 'ring-2 ring-offset-2' : ''}
                `}
                style={{
                  borderColor: getStatusColor(phase.status),
                  ringColor: getStatusColor(phase.status),
                }}
              >
                {getStatusIcon(phase.status)}
              </button>

              {/* Connector line */}
              {index < phases.length - 1 && (
                <div
                  className="w-0.5 flex-1 min-h-[40px]"
                  style={{
                    backgroundColor:
                      phase.status === 'completed'
                        ? 'var(--color-neo-done)'
                        : 'var(--color-neo-border)',
                  }}
                />
              )}
            </div>

            {/* Right side: content */}
            <button
              onClick={() => onPhaseClick?.(phase)}
              className={`
                flex-1 neo-card p-3 text-left
                ${onPhaseClick ? 'hover:border-[var(--color-neo-accent)]' : ''}
                ${currentPhaseId === phase.id ? 'border-[var(--color-neo-accent)] border-2' : ''}
              `}
            >
              <div className="flex items-center justify-between mb-1">
                <div className="text-xs font-mono text-[var(--color-neo-text-secondary)]">
                  Phase {phase.order + 1}
                </div>
                <span
                  className="neo-badge text-xs"
                  style={{
                    backgroundColor: getStatusColor(phase.status),
                    color: 'white',
                  }}
                >
                  {phase.percentage}%
                </span>
              </div>
              <div className="font-bold">{phase.name}</div>
              <div className="text-xs text-[var(--color-neo-text-secondary)] mt-1">
                {phase.passing_tasks}/{phase.total_tasks} tasks completed
              </div>
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
