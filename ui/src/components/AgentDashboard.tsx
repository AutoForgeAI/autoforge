import { useState } from 'react'
import {
  Bot,
  Play,
  Pause,
  Square,
  RefreshCw,
  Terminal,
  Clock,
  CheckCircle2,
  AlertCircle,
  Zap,
} from 'lucide-react'

// Agent types
export type AgentType = 'architect' | 'initializer' | 'coding' | 'reviewer' | 'testing'
export type AgentState = 'idle' | 'running' | 'paused' | 'stopped' | 'crashed'

export interface AgentInfo {
  id: string
  type: AgentType
  state: AgentState
  projectName: string
  currentTaskId?: number
  currentTaskName?: string
  startedAt?: string
  lastActivity?: string
  tokensUsed?: number
  tasksCompleted?: number
  errors?: number
}

interface AgentDashboardProps {
  agents: AgentInfo[]
  logs: Record<string, string[]>  // agent_id -> log lines
  onStartAgent?: (agentId: string) => void
  onPauseAgent?: (agentId: string) => void
  onStopAgent?: (agentId: string) => void
  onRestartAgent?: (agentId: string) => void
  selectedAgentId?: string
  onSelectAgent?: (agentId: string) => void
}

function getAgentTypeConfig(type: AgentType) {
  const configs = {
    architect: {
      label: 'Architect',
      color: '#8338ec',
      icon: '🏗️',
      description: 'Designs system architecture',
    },
    initializer: {
      label: 'Initializer',
      color: '#3a86ff',
      icon: '🚀',
      description: 'Sets up project and creates tasks',
    },
    coding: {
      label: 'Coding',
      color: '#70e000',
      icon: '💻',
      description: 'Implements features and tasks',
    },
    reviewer: {
      label: 'Reviewer',
      color: '#ff006e',
      icon: '👁️',
      description: 'Reviews code quality',
    },
    testing: {
      label: 'Testing',
      color: '#ffd60a',
      icon: '🧪',
      description: 'Runs tests and verification',
    },
  }
  return configs[type] || configs.coding
}

function getStateConfig(state: AgentState) {
  const configs = {
    idle: { label: 'Idle', color: 'text-gray-500', bg: 'bg-gray-100' },
    running: { label: 'Running', color: 'text-green-600', bg: 'bg-green-100' },
    paused: { label: 'Paused', color: 'text-amber-600', bg: 'bg-amber-100' },
    stopped: { label: 'Stopped', color: 'text-gray-600', bg: 'bg-gray-100' },
    crashed: { label: 'Crashed', color: 'text-red-600', bg: 'bg-red-100' },
  }
  return configs[state] || configs.idle
}

function AgentCard({
  agent,
  isSelected,
  onSelect,
  onStart,
  onPause,
  onStop,
  onRestart,
}: {
  agent: AgentInfo
  isSelected: boolean
  onSelect: () => void
  onStart?: () => void
  onPause?: () => void
  onStop?: () => void
  onRestart?: () => void
}) {
  const typeConfig = getAgentTypeConfig(agent.type)
  const stateConfig = getStateConfig(agent.state)

  return (
    <div
      onClick={onSelect}
      className={`
        neo-card p-4 cursor-pointer transition-all
        ${isSelected ? 'border-[var(--color-neo-accent)] border-2 shadow-lg' : ''}
        ${agent.state === 'crashed' ? 'border-red-500' : ''}
      `}
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center text-xl"
            style={{ backgroundColor: `${typeConfig.color}20` }}
          >
            {typeConfig.icon}
          </div>
          <div>
            <div className="font-bold">{typeConfig.label}</div>
            <div className="text-xs text-[var(--color-neo-text-secondary)]">
              {agent.projectName}
            </div>
          </div>
        </div>
        <span className={`neo-badge ${stateConfig.bg} ${stateConfig.color}`}>
          {stateConfig.label}
        </span>
      </div>

      {/* Current Task */}
      {agent.currentTaskName && (
        <div className="mb-3 p-2 bg-[var(--color-neo-bg)] rounded text-sm">
          <div className="text-xs text-[var(--color-neo-text-secondary)]">Current Task</div>
          <div className="font-medium truncate">{agent.currentTaskName}</div>
        </div>
      )}

      {/* Stats */}
      <div className="flex items-center gap-4 text-xs text-[var(--color-neo-text-secondary)] mb-3">
        {agent.tokensUsed !== undefined && (
          <span className="flex items-center gap-1">
            <Zap size={12} />
            {(agent.tokensUsed / 1000).toFixed(0)}K tokens
          </span>
        )}
        {agent.tasksCompleted !== undefined && (
          <span className="flex items-center gap-1">
            <CheckCircle2 size={12} />
            {agent.tasksCompleted} tasks
          </span>
        )}
        {agent.errors !== undefined && agent.errors > 0 && (
          <span className="flex items-center gap-1 text-red-500">
            <AlertCircle size={12} />
            {agent.errors} errors
          </span>
        )}
      </div>

      {/* Time */}
      {agent.startedAt && (
        <div className="text-xs text-[var(--color-neo-text-secondary)] mb-3 flex items-center gap-1">
          <Clock size={12} />
          Started {new Date(agent.startedAt).toLocaleTimeString()}
        </div>
      )}

      {/* Controls */}
      <div className="flex gap-2">
        {agent.state === 'running' && onPause && (
          <button
            onClick={(e) => { e.stopPropagation(); onPause(); }}
            className="neo-button flex-1 flex items-center justify-center gap-1 text-sm"
          >
            <Pause size={14} />
            Pause
          </button>
        )}
        {(agent.state === 'paused' || agent.state === 'idle') && onStart && (
          <button
            onClick={(e) => { e.stopPropagation(); onStart(); }}
            className="neo-button flex-1 flex items-center justify-center gap-1 text-sm bg-green-500 text-white"
          >
            <Play size={14} />
            {agent.state === 'paused' ? 'Resume' : 'Start'}
          </button>
        )}
        {agent.state === 'running' && onStop && (
          <button
            onClick={(e) => { e.stopPropagation(); onStop(); }}
            className="neo-button flex-1 flex items-center justify-center gap-1 text-sm bg-red-500 text-white"
          >
            <Square size={14} />
            Stop
          </button>
        )}
        {agent.state === 'crashed' && onRestart && (
          <button
            onClick={(e) => { e.stopPropagation(); onRestart(); }}
            className="neo-button flex-1 flex items-center justify-center gap-1 text-sm bg-amber-500 text-white"
          >
            <RefreshCw size={14} />
            Restart
          </button>
        )}
      </div>
    </div>
  )
}

function LogViewer({ logs, agentId }: { logs: string[]; agentId: string }) {
  if (!logs || logs.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-[var(--color-neo-text-secondary)]">
        No logs available
      </div>
    )
  }

  return (
    <div className="h-full overflow-auto font-mono text-sm bg-gray-900 text-gray-100 p-4 rounded-lg">
      {logs.map((line, i) => (
        <div key={`${agentId}-${i}`} className="whitespace-pre-wrap">
          {line}
        </div>
      ))}
    </div>
  )
}

export function AgentDashboard({
  agents,
  logs,
  onStartAgent,
  onPauseAgent,
  onStopAgent,
  onRestartAgent,
  selectedAgentId,
  onSelectAgent,
}: AgentDashboardProps) {
  const [localSelectedId, setLocalSelectedId] = useState<string | null>(null)

  const effectiveSelectedId = selectedAgentId ?? localSelectedId
  const handleSelect = onSelectAgent ?? setLocalSelectedId

  const selectedAgent = agents.find(a => a.id === effectiveSelectedId)
  const selectedLogs = effectiveSelectedId ? logs[effectiveSelectedId] || [] : []

  // Group agents by state
  const runningAgents = agents.filter(a => a.state === 'running')
  const otherAgents = agents.filter(a => a.state !== 'running')

  if (agents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Bot size={48} className="text-[var(--color-neo-text-secondary)] mb-4" />
        <h3 className="font-display font-bold text-lg mb-2">No Agents Active</h3>
        <p className="text-[var(--color-neo-text-secondary)] max-w-md">
          Start an agent to begin autonomous development.
        </p>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col lg:flex-row gap-4 p-4">
      {/* Agent List */}
      <div className="lg:w-1/3 space-y-4 overflow-auto">
        <div className="flex items-center gap-2 mb-2">
          <Bot size={20} />
          <h3 className="font-bold">Active Agents</h3>
          <span className="neo-badge bg-green-500 text-white">
            {runningAgents.length} running
          </span>
        </div>

        {/* Running agents first */}
        {runningAgents.map(agent => (
          <AgentCard
            key={agent.id}
            agent={agent}
            isSelected={effectiveSelectedId === agent.id}
            onSelect={() => handleSelect(agent.id)}
            onStart={onStartAgent ? () => onStartAgent(agent.id) : undefined}
            onPause={onPauseAgent ? () => onPauseAgent(agent.id) : undefined}
            onStop={onStopAgent ? () => onStopAgent(agent.id) : undefined}
            onRestart={onRestartAgent ? () => onRestartAgent(agent.id) : undefined}
          />
        ))}

        {/* Other agents */}
        {otherAgents.length > 0 && runningAgents.length > 0 && (
          <div className="text-sm text-[var(--color-neo-text-secondary)] pt-2">
            Other Agents
          </div>
        )}
        {otherAgents.map(agent => (
          <AgentCard
            key={agent.id}
            agent={agent}
            isSelected={effectiveSelectedId === agent.id}
            onSelect={() => handleSelect(agent.id)}
            onStart={onStartAgent ? () => onStartAgent(agent.id) : undefined}
            onPause={onPauseAgent ? () => onPauseAgent(agent.id) : undefined}
            onStop={onStopAgent ? () => onStopAgent(agent.id) : undefined}
            onRestart={onRestartAgent ? () => onRestartAgent(agent.id) : undefined}
          />
        ))}
      </div>

      {/* Log Viewer */}
      <div className="lg:w-2/3 flex flex-col">
        <div className="flex items-center gap-2 mb-2">
          <Terminal size={20} />
          <h3 className="font-bold">
            {selectedAgent ? `Logs: ${getAgentTypeConfig(selectedAgent.type).label}` : 'Logs'}
          </h3>
        </div>
        <div className="flex-1 neo-card p-0 overflow-hidden min-h-[300px]">
          {effectiveSelectedId ? (
            <LogViewer logs={selectedLogs} agentId={effectiveSelectedId} />
          ) : (
            <div className="h-full flex items-center justify-center text-[var(--color-neo-text-secondary)]">
              Select an agent to view logs
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
