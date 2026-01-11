/**
 * Assistant Quick Actions Component
 *
 * Provides quick action buttons for common assistant operations.
 * These can be clicked to send pre-formatted messages to the assistant.
 */

import {
  Play,
  Square,
  Pause,
  Plus,
  BarChart3,
  Zap,
  ArrowUpCircle,
  ListTodo,
  GitBranch,
  CheckCircle,
} from 'lucide-react'

export interface QuickAction {
  id: string
  label: string
  icon: React.ReactNode
  message: string
  variant?: 'default' | 'primary' | 'success' | 'warning'
}

interface AssistantQuickActionsProps {
  onActionClick: (message: string) => void
  disabled?: boolean
  agentStatus?: 'running' | 'paused' | 'stopped'
}

const QUICK_ACTIONS: QuickAction[] = [
  {
    id: 'status',
    label: 'Project Status',
    icon: <BarChart3 size={14} />,
    message: "What's the current status of the project? Show me progress on phases and tasks.",
    variant: 'default',
  },
  {
    id: 'add-feature',
    label: 'Add Feature',
    icon: <Plus size={14} />,
    message: "I want to add a new feature to the project. Let's discuss what it should do.",
    variant: 'primary',
  },
  {
    id: 'start-agent',
    label: 'Start Agent',
    icon: <Play size={14} />,
    message: 'Start the coding agent to work on pending tasks.',
    variant: 'success',
  },
  {
    id: 'stop-agent',
    label: 'Stop Agent',
    icon: <Square size={14} />,
    message: 'Stop the coding agent.',
    variant: 'warning',
  },
  {
    id: 'pause-agent',
    label: 'Pause Agent',
    icon: <Pause size={14} />,
    message: 'Pause the coding agent so I can review progress.',
    variant: 'default',
  },
  {
    id: 'yolo-mode',
    label: 'YOLO Mode',
    icon: <Zap size={14} />,
    message: 'Start the agent in YOLO mode for rapid prototyping without browser tests.',
    variant: 'warning',
  },
  {
    id: 'next-task',
    label: 'Next Task',
    icon: <ListTodo size={14} />,
    message: "What's the next task that needs to be worked on?",
    variant: 'default',
  },
  {
    id: 'dependencies',
    label: 'Check Dependencies',
    icon: <GitBranch size={14} />,
    message: 'Are there any blocked tasks due to dependencies?',
    variant: 'default',
  },
  {
    id: 'migration',
    label: 'Check Migration',
    icon: <ArrowUpCircle size={14} />,
    message: 'Check if this project needs to be migrated to the v2 schema.',
    variant: 'default',
  },
  {
    id: 'submit-phase',
    label: 'Submit Phase',
    icon: <CheckCircle size={14} />,
    message: 'Is the current phase ready to be submitted for approval?',
    variant: 'success',
  },
]

export function AssistantQuickActions({
  onActionClick,
  disabled = false,
  agentStatus = 'stopped',
}: AssistantQuickActionsProps) {
  // Filter actions based on agent status
  const availableActions = QUICK_ACTIONS.filter((action) => {
    if (agentStatus === 'running') {
      // When running, show stop/pause but not start
      return action.id !== 'start-agent' && action.id !== 'yolo-mode'
    } else if (agentStatus === 'paused') {
      // When paused, show start but not pause
      return action.id !== 'pause-agent' && action.id !== 'yolo-mode'
    } else {
      // When stopped, show start but not stop/pause
      return action.id !== 'stop-agent' && action.id !== 'pause-agent'
    }
  })

  const getVariantClasses = (variant: string = 'default') => {
    switch (variant) {
      case 'primary':
        return 'bg-[var(--color-neo-accent)] text-white border-[var(--color-neo-accent)] hover:bg-[var(--color-neo-accent)]/90'
      case 'success':
        return 'bg-[var(--color-neo-done)] text-black border-[var(--color-neo-done)] hover:bg-[var(--color-neo-done)]/90'
      case 'warning':
        return 'bg-[var(--color-neo-pending)] text-black border-[var(--color-neo-pending)] hover:bg-[var(--color-neo-pending)]/90'
      default:
        return 'bg-white text-[var(--color-neo-text)] border-[var(--color-neo-border)] hover:bg-[var(--color-neo-bg)]'
    }
  }

  return (
    <div className="px-4 py-3 border-b-2 border-[var(--color-neo-border)] bg-white">
      <div className="flex items-center gap-2 mb-2">
        <span className="text-xs font-bold text-[var(--color-neo-text-secondary)] uppercase tracking-wider">
          Quick Actions
        </span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {availableActions.map((action) => (
          <button
            key={action.id}
            onClick={() => onActionClick(action.message)}
            disabled={disabled}
            className={`
              inline-flex items-center gap-1.5
              px-2.5 py-1.5
              text-xs font-medium
              border-2 rounded
              shadow-[2px_2px_0px_rgba(0,0,0,1)]
              transition-all duration-100
              hover:shadow-[1px_1px_0px_rgba(0,0,0,1)]
              hover:translate-x-[1px] hover:translate-y-[1px]
              active:shadow-none active:translate-x-[2px] active:translate-y-[2px]
              disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:shadow-[2px_2px_0px_rgba(0,0,0,1)] disabled:hover:translate-x-0 disabled:hover:translate-y-0
              ${getVariantClasses(action.variant)}
            `}
            title={action.message}
          >
            {action.icon}
            <span>{action.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
