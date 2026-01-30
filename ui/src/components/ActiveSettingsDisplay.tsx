import { Zap, Users, FlaskConical, Cpu } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type { Settings, AgentStatusResponse } from '../lib/types'

interface ActiveSettingsDisplayProps {
  settings?: Settings
  agentStatus?: AgentStatusResponse
  isRunning?: boolean
}

/**
 * Displays active settings when agent is running
 * Shows: YOLO mode, # coders, # testers, model
 */
export function ActiveSettingsDisplay({
  settings,
  agentStatus,
  isRunning = false
}: ActiveSettingsDisplayProps) {
  if (!isRunning || !agentStatus) {
    return null
  }

  const yoloMode = agentStatus.yolo_mode
  const model = agentStatus.model || settings?.model || 'default'
  const maxConcurrency = agentStatus.max_concurrency || 1
  const testingRatio = agentStatus.testing_agent_ratio ?? settings?.testing_agent_ratio ?? 1

  // Shorten model name for display
  const displayModel = model
    .replace('claude-', '')
    .replace('-20251101', '')
    .replace('claude-3-5-', '')
    .replace('claude-3-', '')

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      {/* YOLO Mode */}
      {yoloMode && (
        <Badge variant="destructive" className="flex items-center gap-1">
          <Zap size={12} />
          YOLO
        </Badge>
      )}

      {/* Model */}
      <Badge variant="outline" className="flex items-center gap-1">
        <Cpu size={12} />
        {displayModel}
      </Badge>

      {/* Coders */}
      <Badge variant="secondary" className="flex items-center gap-1">
        <Users size={12} />
        {maxConcurrency} coder{maxConcurrency !== 1 ? 's' : ''}
      </Badge>

      {/* Testers (only if not YOLO and ratio > 0) */}
      {!yoloMode && testingRatio > 0 && (
        <Badge variant="secondary" className="flex items-center gap-1">
          <FlaskConical size={12} />
          {testingRatio} tester{testingRatio !== 1 ? 's' : ''}
        </Badge>
      )}
    </div>
  )
}
