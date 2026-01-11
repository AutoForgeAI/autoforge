import {
  CheckCircle2,
  Circle,
  Clock,
  AlertCircle,
  XCircle,
  ChevronRight,
  BarChart3,
} from 'lucide-react'

export type PhaseStatus = 'pending' | 'in_progress' | 'awaiting_approval' | 'completed' | 'rejected'

export interface PhaseData {
  id: number
  name: string
  order: number
  status: PhaseStatus
  total_tasks: number
  passing_tasks: number
  percentage: number
  created_at?: string | null
  completed_at?: string | null
}

interface PhaseCardProps {
  phase: PhaseData
  onClick?: () => void
  onApprove?: () => void
  onReject?: () => void
  isExpanded?: boolean
}

function getStatusConfig(status: PhaseStatus) {
  switch (status) {
    case 'completed':
      return {
        icon: CheckCircle2,
        color: 'var(--color-neo-done)',
        bgColor: 'bg-green-50',
        borderColor: 'border-green-500',
        label: 'Completed',
      }
    case 'in_progress':
      return {
        icon: Clock,
        color: 'var(--color-neo-progress)',
        bgColor: 'bg-cyan-50',
        borderColor: 'border-cyan-500',
        label: 'In Progress',
      }
    case 'awaiting_approval':
      return {
        icon: AlertCircle,
        color: '#f59e0b',
        bgColor: 'bg-amber-50',
        borderColor: 'border-amber-500',
        label: 'Awaiting Approval',
      }
    case 'rejected':
      return {
        icon: XCircle,
        color: '#ef4444',
        bgColor: 'bg-red-50',
        borderColor: 'border-red-500',
        label: 'Rejected',
      }
    case 'pending':
    default:
      return {
        icon: Circle,
        color: 'var(--color-neo-text-secondary)',
        bgColor: 'bg-gray-50',
        borderColor: 'border-gray-300',
        label: 'Pending',
      }
  }
}

export function PhaseCard({
  phase,
  onClick,
  onApprove,
  onReject,
  isExpanded = false,
}: PhaseCardProps) {
  const config = getStatusConfig(phase.status)
  const StatusIcon = config.icon

  return (
    <div
      className={`
        neo-card p-4 ${config.bgColor} ${config.borderColor}
        ${onClick ? 'cursor-pointer hover:shadow-lg transition-shadow' : ''}
      `}
      onClick={onClick}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div
            className="p-1.5 rounded-lg"
            style={{ backgroundColor: `${config.color}20` }}
          >
            <StatusIcon size={18} style={{ color: config.color }} />
          </div>
          <div>
            <div className="text-xs text-[var(--color-neo-text-secondary)] font-mono">
              Phase {phase.order + 1}
            </div>
            <h3 className="font-display font-bold">{phase.name}</h3>
          </div>
        </div>
        {onClick && (
          <ChevronRight
            size={20}
            className={`text-[var(--color-neo-text-secondary)] transition-transform ${
              isExpanded ? 'rotate-90' : ''
            }`}
          />
        )}
      </div>

      {/* Progress Bar */}
      <div className="mb-3">
        <div className="flex items-center justify-between text-sm mb-1">
          <span className="text-[var(--color-neo-text-secondary)]">Progress</span>
          <span className="font-bold">{phase.percentage}%</span>
        </div>
        <div className="h-2 bg-[var(--color-neo-border)] rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${phase.percentage}%`,
              backgroundColor: config.color,
            }}
          />
        </div>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-4 text-sm">
        <div className="flex items-center gap-1">
          <BarChart3 size={14} className="text-[var(--color-neo-text-secondary)]" />
          <span>
            {phase.passing_tasks}/{phase.total_tasks} tasks
          </span>
        </div>
        <span
          className="neo-badge text-xs"
          style={{ backgroundColor: config.color, color: 'white' }}
        >
          {config.label}
        </span>
      </div>

      {/* Approval Actions */}
      {phase.status === 'awaiting_approval' && (onApprove || onReject) && (
        <div className="flex gap-2 mt-3 pt-3 border-t border-[var(--color-neo-border)]">
          {onApprove && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onApprove()
              }}
              className="neo-button flex-1 bg-green-500 text-white hover:bg-green-600"
            >
              Approve
            </button>
          )}
          {onReject && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                onReject()
              }}
              className="neo-button flex-1 bg-red-500 text-white hover:bg-red-600"
            >
              Reject
            </button>
          )}
        </div>
      )}

      {/* Completion Date */}
      {phase.completed_at && (
        <div className="mt-2 text-xs text-[var(--color-neo-text-secondary)]">
          Completed: {new Date(phase.completed_at).toLocaleDateString()}
        </div>
      )}
    </div>
  )
}
