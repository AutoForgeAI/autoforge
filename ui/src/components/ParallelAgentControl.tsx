import { useState } from 'react'
import {
  Play,
  Square,
  Loader2,
  Zap,
  Users,
  Bot,
  GitMerge,
  Trash2,
  Minus,
  Plus,
} from 'lucide-react'
import {
  useParallelAgentsStatus,
  useStartParallelAgents,
  useStopParallelAgents,
  useMergeParallelWorktrees,
  useCleanupParallelAgents,
} from '../hooks/useProjects'
import type { ParallelAgentInfo } from '../lib/types'

interface ParallelAgentControlProps {
  projectName: string
  onModeChange?: (isParallel: boolean) => void
}

// Agent colors matching FeatureCard.tsx
const AGENT_COLORS = [
  '#00b4d8', // cyan - agent-1
  '#70e000', // green - agent-2
  '#8338ec', // purple - agent-3
  '#ff5400', // orange - agent-4
  '#ff006e', // pink - agent-5
]

function getAgentColor(agentId: string): string {
  const match = agentId.match(/\d+/)
  if (match) {
    const num = parseInt(match[0], 10) - 1
    return AGENT_COLORS[num % AGENT_COLORS.length]
  }
  return AGENT_COLORS[0]
}

export function ParallelAgentControl({
  projectName,
  onModeChange,
}: ParallelAgentControlProps) {
  const [numAgents, setNumAgents] = useState(2)
  const [yoloEnabled, setYoloEnabled] = useState(false)
  const [isParallelMode, setIsParallelMode] = useState(false)

  const { data: status, isLoading: statusLoading } = useParallelAgentsStatus(
    isParallelMode ? projectName : null
  )

  const startAgents = useStartParallelAgents(projectName)
  const stopAgents = useStopParallelAgents(projectName)
  const mergeWorktrees = useMergeParallelWorktrees(projectName)
  const cleanupAgents = useCleanupParallelAgents(projectName)

  const isLoading =
    startAgents.isPending ||
    stopAgents.isPending ||
    mergeWorktrees.isPending ||
    cleanupAgents.isPending

  const hasRunningAgents = (status?.total_running ?? 0) > 0

  const handleToggleMode = () => {
    const newMode = !isParallelMode
    setIsParallelMode(newMode)
    onModeChange?.(newMode)
  }

  const handleStart = () => {
    startAgents.mutate({ numAgents, yoloMode: yoloEnabled })
  }

  const handleStop = () => {
    stopAgents.mutate()
  }

  const handleMerge = () => {
    mergeWorktrees.mutate()
  }

  const handleCleanup = () => {
    cleanupAgents.mutate()
  }

  if (!isParallelMode) {
    return (
      <button
        onClick={handleToggleMode}
        className="neo-btn neo-btn-secondary text-sm py-2 px-3 flex items-center gap-2"
        title="Switch to Parallel Agents Mode"
      >
        <Users size={16} />
        <span className="hidden sm:inline">Parallel</span>
      </button>
    )
  }

  return (
    <div className="flex flex-col gap-3 p-4 bg-white border-3 border-[var(--color-neo-border)] shadow-neo">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Users size={18} className="text-[var(--color-neo-primary)]" />
          <span className="font-display font-bold text-sm uppercase">
            Parallel Agents
          </span>
        </div>
        <button
          onClick={handleToggleMode}
          className="text-xs text-[var(--color-neo-text-secondary)] hover:text-[var(--color-neo-text)] underline"
        >
          Single Mode
        </button>
      </div>

      {/* Agent Status Grid */}
      {status && status.agents.length > 0 && (
        <div className="grid grid-cols-5 gap-2">
          {status.agents.map((agent) => (
            <AgentStatusBadge key={agent.agent_id} agent={agent} />
          ))}
        </div>
      )}

      {/* Controls */}
      {!hasRunningAgents ? (
        <div className="flex flex-col gap-2">
          {/* Agent Count Selector */}
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Agents:</span>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setNumAgents(Math.max(1, numAgents - 1))}
                className="neo-btn neo-btn-secondary p-1"
                disabled={numAgents <= 1}
              >
                <Minus size={14} />
              </button>
              <span className="w-8 text-center font-bold text-lg">{numAgents}</span>
              <button
                onClick={() => setNumAgents(Math.min(5, numAgents + 1))}
                className="neo-btn neo-btn-secondary p-1"
                disabled={numAgents >= 5}
              >
                <Plus size={14} />
              </button>
            </div>

            {/* YOLO Toggle */}
            <button
              onClick={() => setYoloEnabled(!yoloEnabled)}
              className={`neo-btn text-sm py-1 px-2 ml-auto ${
                yoloEnabled ? 'neo-btn-warning' : 'neo-btn-secondary'
              }`}
              title="YOLO Mode: Skip testing for rapid prototyping"
            >
              <Zap size={14} className={yoloEnabled ? 'text-yellow-900' : ''} />
            </button>
          </div>

          {/* Start Button */}
          <button
            onClick={handleStart}
            disabled={isLoading}
            className="neo-btn neo-btn-success text-sm py-2 px-4 flex items-center justify-center gap-2"
          >
            {isLoading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <>
                <Play size={16} />
                Start {numAgents} Agents
              </>
            )}
          </button>
        </div>
      ) : (
        <div className="flex flex-col gap-2">
          {/* Running indicator */}
          <div className="flex items-center gap-2 text-sm">
            <span
              className="w-2 h-2 rounded-full bg-[var(--color-neo-done)] animate-pulse"
            />
            <span className="text-[var(--color-neo-text-secondary)]">
              {status?.total_running} agent{status?.total_running !== 1 ? 's' : ''} running
            </span>
            {yoloEnabled && (
              <div className="flex items-center gap-1 px-2 py-0.5 bg-[var(--color-neo-pending)] border border-yellow-600 rounded">
                <Zap size={12} className="text-yellow-900" />
                <span className="text-xs font-bold text-yellow-900">YOLO</span>
              </div>
            )}
          </div>

          {/* Action Buttons */}
          <div className="flex gap-2">
            <button
              onClick={handleStop}
              disabled={isLoading}
              className="neo-btn neo-btn-danger text-sm py-2 px-3 flex items-center gap-1 flex-1"
              title="Stop All Agents"
            >
              {stopAgents.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Square size={14} />
              )}
              <span>Stop</span>
            </button>
            <button
              onClick={handleMerge}
              disabled={isLoading}
              className="neo-btn neo-btn-primary text-sm py-2 px-3 flex items-center gap-1 flex-1"
              title="Merge Worktree Changes"
            >
              {mergeWorktrees.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <GitMerge size={14} />
              )}
              <span>Merge</span>
            </button>
            <button
              onClick={handleCleanup}
              disabled={isLoading}
              className="neo-btn neo-btn-secondary text-sm py-2 px-3 flex items-center gap-1"
              title="Stop All & Cleanup Worktrees"
            >
              {cleanupAgents.isPending ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Trash2 size={14} />
              )}
            </button>
          </div>
        </div>
      )}

      {/* Status Loading */}
      {statusLoading && !status && (
        <div className="flex items-center justify-center py-2">
          <Loader2 size={16} className="animate-spin text-[var(--color-neo-text-secondary)]" />
        </div>
      )}
    </div>
  )
}

function AgentStatusBadge({ agent }: { agent: ParallelAgentInfo }) {
  const color = getAgentColor(agent.agent_id)
  const statusColors: Record<string, string> = {
    running: 'var(--color-neo-done)',
    paused: 'var(--color-neo-pending)',
    stopped: 'var(--color-neo-text-secondary)',
    crashed: 'var(--color-neo-danger)',
    unknown: 'var(--color-neo-text-secondary)',
  }

  const statusColor = statusColors[agent.status] || statusColors.unknown
  const agentNum = agent.agent_id.replace('agent-', '#')

  return (
    <div
      className="flex flex-col items-center gap-1 p-2 rounded border-2"
      style={{ borderColor: color }}
      title={`${agent.agent_id}: ${agent.status}${agent.worktree_path ? `\nWorktree: ${agent.worktree_path}` : ''}`}
    >
      <Bot size={16} style={{ color }} />
      <span className="text-xs font-bold" style={{ color }}>
        {agentNum}
      </span>
      <span
        className={`w-2 h-2 rounded-full ${agent.status === 'running' ? 'animate-pulse' : ''}`}
        style={{ backgroundColor: statusColor }}
      />
    </div>
  )
}
