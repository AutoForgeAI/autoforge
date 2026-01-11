import { useState } from 'react'
import {
  ChevronRight,
  ChevronDown,
  BarChart3,
  CheckCircle2,
  Clock,
  Lock,
  Package,
} from 'lucide-react'
import type { Feature } from '../lib/types'

// Feature group (collection of tasks)
export interface FeatureGroup {
  id: number
  name: string
  description?: string
  tasks: Feature[]
  total_tasks: number
  passing_tasks: number
  percentage: number
}

interface FeatureListProps {
  features: FeatureGroup[]
  onFeatureClick?: (feature: FeatureGroup) => void
  onTaskClick?: (task: Feature) => void
  expandedFeatureId?: number | null
  onToggleExpand?: (featureId: number) => void
}

function FeatureRow({
  feature,
  isExpanded,
  onToggle,
  onClick,
  onTaskClick,
}: {
  feature: FeatureGroup
  isExpanded: boolean
  onToggle: () => void
  onClick?: () => void
  onTaskClick?: (task: Feature) => void
}) {
  const isComplete = feature.percentage === 100
  const hasProgress = feature.percentage > 0

  return (
    <div className="neo-card overflow-hidden">
      {/* Feature Header */}
      <div
        className={`
          flex items-center gap-3 p-3 cursor-pointer
          hover:bg-[var(--color-neo-bg)] transition-colors
          ${isComplete ? 'bg-green-50' : ''}
        `}
        onClick={onClick ?? onToggle}
      >
        {/* Expand Toggle */}
        <button
          onClick={(e) => {
            e.stopPropagation()
            onToggle()
          }}
          className="p-1 hover:bg-[var(--color-neo-border)] rounded"
        >
          {isExpanded ? (
            <ChevronDown size={18} />
          ) : (
            <ChevronRight size={18} />
          )}
        </button>

        {/* Icon */}
        <div className={`
          p-2 rounded-lg flex-shrink-0
          ${isComplete ? 'bg-green-100 text-green-600' : 'bg-[var(--color-neo-bg)]'}
        `}>
          <Package size={18} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h4 className="font-bold truncate">{feature.name}</h4>
            {isComplete && (
              <CheckCircle2 size={16} className="text-[var(--color-neo-done)] flex-shrink-0" />
            )}
          </div>
          {feature.description && (
            <p className="text-xs text-[var(--color-neo-text-secondary)] truncate">
              {feature.description}
            </p>
          )}
        </div>

        {/* Progress */}
        <div className="flex items-center gap-3 flex-shrink-0">
          <div className="text-right">
            <div className="text-sm font-bold">{feature.percentage}%</div>
            <div className="text-xs text-[var(--color-neo-text-secondary)]">
              {feature.passing_tasks}/{feature.total_tasks}
            </div>
          </div>
          <div className="w-24 h-2 bg-[var(--color-neo-border)] rounded-full overflow-hidden hidden sm:block">
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${feature.percentage}%`,
                backgroundColor: isComplete
                  ? 'var(--color-neo-done)'
                  : hasProgress
                    ? 'var(--color-neo-progress)'
                    : 'var(--color-neo-pending)',
              }}
            />
          </div>
        </div>
      </div>

      {/* Expanded Task List */}
      {isExpanded && feature.tasks.length > 0 && (
        <div className="border-t border-[var(--color-neo-border)] bg-[var(--color-neo-bg)]">
          {feature.tasks.map((task, index) => (
            <TaskRow
              key={task.id}
              task={task}
              isLast={index === feature.tasks.length - 1}
              onClick={() => onTaskClick?.(task)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function TaskRow({
  task,
  isLast,
  onClick,
}: {
  task: Feature
  isLast: boolean
  onClick?: () => void
}) {
  const isBlocked = task.is_blocked === true
  const isComplete = task.passes
  const isInProgress = task.in_progress

  const getStatusIcon = () => {
    if (isComplete) return <CheckCircle2 size={14} className="text-[var(--color-neo-done)]" />
    if (isBlocked) return <Lock size={14} className="text-red-500" />
    if (isInProgress) return <Clock size={14} className="text-[var(--color-neo-progress)]" />
    return <div className="w-3.5 h-3.5 rounded-full border-2 border-[var(--color-neo-border)]" />
  }

  return (
    <button
      onClick={onClick}
      className={`
        w-full flex items-center gap-3 px-4 py-2 text-left
        hover:bg-[var(--color-neo-card)] transition-colors
        ${!isLast ? 'border-b border-[var(--color-neo-border)]' : ''}
        ${isBlocked ? 'opacity-60' : ''}
      `}
    >
      {/* Tree connector */}
      <div className="w-4 flex justify-center">
        <div className="w-px h-full bg-[var(--color-neo-border)]" />
      </div>

      {/* Status icon */}
      {getStatusIcon()}

      {/* Task info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className={`text-sm truncate ${isComplete ? 'line-through text-[var(--color-neo-text-secondary)]' : ''}`}>
            {task.name}
          </span>
          <span className="text-xs font-mono text-[var(--color-neo-text-secondary)]">
            #{task.priority}
          </span>
        </div>
        {isBlocked && task.blocked_reason && (
          <p className="text-xs text-red-500 truncate">{task.blocked_reason}</p>
        )}
      </div>

      {/* Category badge */}
      <span className="neo-badge text-xs bg-[var(--color-neo-bg)]">
        {task.category}
      </span>

      {/* Navigate arrow */}
      <ChevronRight size={16} className="text-[var(--color-neo-text-secondary)]" />
    </button>
  )
}

export function FeatureList({
  features,
  onFeatureClick,
  onTaskClick,
  expandedFeatureId,
  onToggleExpand,
}: FeatureListProps) {
  const [localExpanded, setLocalExpanded] = useState<number | null>(null)

  const expanded = expandedFeatureId ?? localExpanded
  const handleToggle = onToggleExpand ?? setLocalExpanded

  if (features.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Package size={48} className="text-[var(--color-neo-text-secondary)] mb-4" />
        <h3 className="font-display font-bold text-lg mb-2">No Features Yet</h3>
        <p className="text-[var(--color-neo-text-secondary)] max-w-md">
          Features will appear here once they are created.
        </p>
      </div>
    )
  }

  // Summary stats
  const totalTasks = features.reduce((sum, f) => sum + f.total_tasks, 0)
  const passingTasks = features.reduce((sum, f) => sum + f.passing_tasks, 0)
  const overallPercentage = totalTasks > 0 ? (passingTasks / totalTasks) * 100 : 0

  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="flex items-center justify-between px-4 py-2 bg-[var(--color-neo-bg)] rounded-lg">
        <div className="flex items-center gap-4 text-sm">
          <span className="font-bold">{features.length} Features</span>
          <span className="text-[var(--color-neo-text-secondary)]">
            {passingTasks}/{totalTasks} tasks complete
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-32 h-2 bg-[var(--color-neo-border)] rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-[var(--color-neo-progress)]"
              style={{ width: `${overallPercentage}%` }}
            />
          </div>
          <span className="text-sm font-bold">{overallPercentage.toFixed(0)}%</span>
        </div>
      </div>

      {/* Feature List */}
      <div className="space-y-2">
        {features.map(feature => (
          <FeatureRow
            key={feature.id}
            feature={feature}
            isExpanded={expanded === feature.id}
            onToggle={() => handleToggle(expanded === feature.id ? null : feature.id)}
            onClick={onFeatureClick ? () => onFeatureClick(feature) : undefined}
            onTaskClick={onTaskClick}
          />
        ))}
      </div>
    </div>
  )
}
