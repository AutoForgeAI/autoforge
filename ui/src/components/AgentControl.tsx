import { useState } from 'react'
import { Play, Square, Loader2, GitBranch, Clock } from 'lucide-react'
import {
  useStartAgent,
  useStopAgent,
  useSettings,
} from '../hooks/useProjects'
import { useNextScheduledRun } from '../hooks/useSchedules'
import { formatNextRun, formatEndTime } from '../lib/timeUtils'
import { ScheduleModal } from './ScheduleModal'
import type { AgentStatus } from '../lib/types'

interface AgentControlProps {
  projectName: string
  status: AgentStatus
}

export function AgentControl({ projectName, status }: AgentControlProps) {
  const { data: settings } = useSettings()
  const yoloMode = settings?.yolo_mode ?? false

  // Concurrency: 1 = single agent, 2-5 = parallel
  const [concurrency, setConcurrency] = useState(3)

  const startAgent = useStartAgent(projectName)
  const stopAgent = useStopAgent(projectName)
  const { data: nextRun } = useNextScheduledRun(projectName)

  const [showScheduleModal, setShowScheduleModal] = useState(false)

  const isLoading = startAgent.isPending || stopAgent.isPending
  const isRunning = status === 'running' || status === 'paused'
  const isLoadingStatus = status === 'loading'  // Status unknown, waiting for WebSocket
  const isParallel = concurrency > 1

  const handleStart = () => startAgent.mutate({
    yoloMode,
    parallelMode: isParallel,
    maxConcurrency: concurrency,  // Always pass concurrency (1-5)
    testingAgentRatio: settings?.testing_agent_ratio,
  })
  const handleStop = () => stopAgent.mutate()

  // Simplified: either show Start (when stopped/crashed), Stop (when running/paused), or loading spinner
  const isStopped = status === 'stopped' || status === 'crashed'

  return (
    <>
      <div className="flex items-center gap-4">
        {/* Concurrency slider - visible when stopped */}
        {isStopped && (
          <div className="flex items-center gap-2">
            <GitBranch size={16} className={isParallel ? 'text-[var(--color-neo-primary)]' : 'text-gray-400'} />
            <input
              type="range"
              min={1}
              max={5}
              value={concurrency}
              onChange={(e) => setConcurrency(Number(e.target.value))}
              disabled={isLoading}
              className="w-16 h-2 accent-[var(--color-neo-primary)] cursor-pointer"
              title={`${concurrency} concurrent agent${concurrency > 1 ? 's' : ''}`}
              aria-label="Set number of concurrent agents"
            />
            <span className="text-xs font-bold min-w-[1.5rem] text-center">
              {concurrency}x
            </span>
          </div>
        )}

        {/* Show concurrency indicator when running with multiple agents */}
        {isRunning && isParallel && (
          <div className="flex items-center gap-1 text-xs text-[var(--color-neo-primary)] font-bold">
            <GitBranch size={14} />
            <span>{concurrency}x</span>
          </div>
        )}

        {/* Schedule status display */}
        {nextRun?.is_currently_running && nextRun.next_end && (
          <div className="flex items-center gap-2 text-sm text-[var(--color-neo-done)] font-bold">
            <Clock size={16} className="flex-shrink-0" />
            <span>Running until {formatEndTime(nextRun.next_end)}</span>
          </div>
        )}

        {!nextRun?.is_currently_running && nextRun?.next_start && (
          <div className="flex items-center gap-2 text-sm text-gray-900 dark:text-white font-bold">
            <Clock size={16} className="flex-shrink-0" />
            <span>Next: {formatNextRun(nextRun.next_start)}</span>
          </div>
        )}

        {/* Start/Stop button */}
        {isLoadingStatus ? (
          <button
            disabled
            className="neo-btn text-sm py-2 px-3 opacity-50 cursor-not-allowed"
            title="Loading agent status..."
            aria-label="Loading agent status"
          >
            <Loader2 size={18} className="animate-spin" />
          </button>
        ) : isStopped ? (
          <button
            onClick={handleStart}
            disabled={isLoading}
            className={`neo-btn text-sm py-2 px-3 ${
              yoloMode ? 'neo-btn-yolo' : 'neo-btn-success'
            }`}
            title={yoloMode ? 'Start Agent (YOLO Mode)' : 'Start Agent'}
            aria-label={yoloMode ? 'Start Agent in YOLO Mode' : 'Start Agent'}
          >
            {isLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Play size={18} />
            )}
          </button>
        ) : (
          <button
            onClick={handleStop}
            disabled={isLoading}
            className={`neo-btn text-sm py-2 px-3 ${
              yoloMode ? 'neo-btn-yolo' : 'neo-btn-danger'
            }`}
            title={yoloMode ? 'Stop Agent (YOLO Mode)' : 'Stop Agent'}
            aria-label={yoloMode ? 'Stop Agent in YOLO Mode' : 'Stop Agent'}
          >
            {isLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Square size={18} />
            )}
          </button>
        )}

        {/* Clock button to open schedule modal */}
        <button
          onClick={() => setShowScheduleModal(true)}
          className="neo-btn text-sm py-2 px-3"
          title="Manage schedules"
          aria-label="Manage agent schedules"
        >
          <Clock size={18} />
        </button>
      </div>

      {/* Schedule Modal */}
      <ScheduleModal
        projectName={projectName}
        isOpen={showScheduleModal}
        onClose={() => setShowScheduleModal(false)}
      />
    </>
  )
}
