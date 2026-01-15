import {
  Play,
  Square,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  ArrowRight,
  MessageSquare,
  Clock,
} from 'lucide-react'
import type { AgentType } from './AgentDashboard'

export type TimelineEventType =
  | 'agent_start'
  | 'agent_stop'
  | 'task_start'
  | 'task_complete'
  | 'task_fail'
  | 'phase_complete'
  | 'handoff'
  | 'message'
  | 'error'

export interface TimelineEvent {
  id: string
  type: TimelineEventType
  timestamp: string
  agentType: AgentType
  agentId: string
  title: string
  description?: string
  metadata?: {
    taskId?: number
    taskName?: string
    phaseId?: number
    phaseName?: string
    fromAgent?: AgentType
    toAgent?: AgentType
    errorMessage?: string
  }
}

interface AgentTimelineProps {
  events: TimelineEvent[]
  maxEvents?: number
  onEventClick?: (event: TimelineEvent) => void
  showFilters?: boolean
}

function getEventConfig(type: TimelineEventType) {
  const configs: Record<TimelineEventType, {
    icon: React.ReactNode
    color: string
    bgColor: string
  }> = {
    agent_start: {
      icon: <Play size={14} />,
      color: 'text-green-600',
      bgColor: 'bg-green-100',
    },
    agent_stop: {
      icon: <Square size={14} />,
      color: 'text-gray-600',
      bgColor: 'bg-gray-100',
    },
    task_start: {
      icon: <Clock size={14} />,
      color: 'text-blue-600',
      bgColor: 'bg-blue-100',
    },
    task_complete: {
      icon: <CheckCircle2 size={14} />,
      color: 'text-green-600',
      bgColor: 'bg-green-100',
    },
    task_fail: {
      icon: <XCircle size={14} />,
      color: 'text-red-600',
      bgColor: 'bg-red-100',
    },
    phase_complete: {
      icon: <CheckCircle2 size={14} />,
      color: 'text-purple-600',
      bgColor: 'bg-purple-100',
    },
    handoff: {
      icon: <ArrowRight size={14} />,
      color: 'text-amber-600',
      bgColor: 'bg-amber-100',
    },
    message: {
      icon: <MessageSquare size={14} />,
      color: 'text-blue-600',
      bgColor: 'bg-blue-100',
    },
    error: {
      icon: <AlertTriangle size={14} />,
      color: 'text-red-600',
      bgColor: 'bg-red-100',
    },
  }
  return configs[type]
}

function getAgentColor(type: AgentType): string {
  const colors: Record<AgentType, string> = {
    architect: '#8338ec',
    initializer: '#3a86ff',
    coding: '#70e000',
    reviewer: '#ff006e',
    testing: '#ffd60a',
  }
  return colors[type] || '#666'
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

function formatDate(timestamp: string): string {
  const date = new Date(timestamp)
  return date.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  })
}

function TimelineEventItem({
  event,
  isLast,
  onClick,
}: {
  event: TimelineEvent
  isLast: boolean
  onClick?: () => void
}) {
  const config = getEventConfig(event.type)
  const agentColor = getAgentColor(event.agentType)

  return (
    <div
      className={`flex gap-3 ${onClick ? 'cursor-pointer hover:bg-[var(--color-neo-bg)]' : ''} p-2 rounded`}
      onClick={onClick}
    >
      {/* Timeline connector */}
      <div className="flex flex-col items-center">
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center ${config.bgColor} ${config.color}`}
        >
          {config.icon}
        </div>
        {!isLast && (
          <div className="w-0.5 flex-1 bg-[var(--color-neo-border)] my-1" />
        )}
      </div>

      {/* Content */}
      <div className="flex-1 pb-4">
        <div className="flex items-center gap-2 mb-1">
          <span
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: agentColor }}
            title={event.agentType}
          />
          <span className="font-bold text-sm">{event.title}</span>
          <span className="text-xs text-[var(--color-neo-text-secondary)]">
            {formatTime(event.timestamp)}
          </span>
        </div>

        {event.description && (
          <p className="text-sm text-[var(--color-neo-text-secondary)]">
            {event.description}
          </p>
        )}

        {/* Metadata badges */}
        {event.metadata && (
          <div className="flex flex-wrap gap-1 mt-1">
            {event.metadata.taskName && (
              <span className="neo-badge text-xs bg-[var(--color-neo-bg)]">
                Task: {event.metadata.taskName}
              </span>
            )}
            {event.metadata.phaseName && (
              <span className="neo-badge text-xs bg-purple-100 text-purple-700">
                Phase: {event.metadata.phaseName}
              </span>
            )}
            {event.metadata.fromAgent && event.metadata.toAgent && (
              <span className="neo-badge text-xs bg-amber-100 text-amber-700">
                {event.metadata.fromAgent} → {event.metadata.toAgent}
              </span>
            )}
          </div>
        )}

        {/* Error message */}
        {event.metadata?.errorMessage && (
          <div className="mt-1 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
            {event.metadata.errorMessage}
          </div>
        )}
      </div>
    </div>
  )
}

export function AgentTimeline({
  events,
  maxEvents = 50,
  onEventClick,
  showFilters = false,
}: AgentTimelineProps) {
  // Group events by date
  const groupedEvents: Record<string, TimelineEvent[]> = {}

  const displayEvents = events.slice(0, maxEvents)

  for (const event of displayEvents) {
    const dateKey = formatDate(event.timestamp)
    if (!groupedEvents[dateKey]) {
      groupedEvents[dateKey] = []
    }
    groupedEvents[dateKey].push(event)
  }

  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Clock size={48} className="text-[var(--color-neo-text-secondary)] mb-4" />
        <h3 className="font-display font-bold text-lg mb-2">No Events Yet</h3>
        <p className="text-[var(--color-neo-text-secondary)] max-w-md">
          Agent activity events will appear here as agents work.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Legend */}
      {showFilters && (
        <div className="flex flex-wrap gap-3 text-xs">
          {(['architect', 'initializer', 'coding', 'reviewer', 'testing'] as AgentType[]).map(type => (
            <div key={type} className="flex items-center gap-1">
              <span
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: getAgentColor(type) }}
              />
              <span className="capitalize">{type}</span>
            </div>
          ))}
        </div>
      )}

      {/* Timeline */}
      {Object.entries(groupedEvents).map(([date, dateEvents]) => (
        <div key={date}>
          {/* Date header */}
          <div className="sticky top-0 bg-[var(--color-neo-card)] py-2 mb-2 border-b border-[var(--color-neo-border)]">
            <span className="font-bold text-sm">{date}</span>
            <span className="text-xs text-[var(--color-neo-text-secondary)] ml-2">
              {dateEvents.length} events
            </span>
          </div>

          {/* Events for this date */}
          {dateEvents.map((event, index) => (
            <TimelineEventItem
              key={event.id}
              event={event}
              isLast={index === dateEvents.length - 1}
              onClick={onEventClick ? () => onEventClick(event) : undefined}
            />
          ))}
        </div>
      ))}

      {/* Load more indicator */}
      {events.length > maxEvents && (
        <div className="text-center text-sm text-[var(--color-neo-text-secondary)]">
          Showing {maxEvents} of {events.length} events
        </div>
      )}
    </div>
  )
}
