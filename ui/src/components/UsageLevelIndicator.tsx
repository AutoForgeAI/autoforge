/**
 * Usage Level Indicator
 *
 * Compact indicator showing current session usage level.
 * Displays in the header bar for at-a-glance status.
 */

import { useQuery } from '@tanstack/react-query'
import { Activity, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { Badge } from '@/components/ui/badge'

interface UsageLevelIndicatorProps {
  projectName: string | null
}

type UsageLevel = 'healthy' | 'moderate' | 'low' | 'critical'

interface SchedulerStatus {
  level: UsageLevel
  strategy: string
  session: {
    messagesSent: number
    messagesLimit: number
    messagesRemaining: number
    messagePercentUsed: number
    contextPercentUsed: number
  }
  overallPercentageUsed: number
  shouldContinue: boolean
  statusMessage: string
}

const LEVEL_CONFIG = {
  healthy: {
    icon: CheckCircle,
    color: 'text-green-500',
    bgColor: 'bg-green-500/10',
    borderColor: 'border-green-500/30',
    label: 'Healthy',
  },
  moderate: {
    icon: Activity,
    color: 'text-yellow-500',
    bgColor: 'bg-yellow-500/10',
    borderColor: 'border-yellow-500/30',
    label: 'Moderate',
  },
  low: {
    icon: AlertTriangle,
    color: 'text-orange-500',
    bgColor: 'bg-orange-500/10',
    borderColor: 'border-orange-500/30',
    label: 'Low',
  },
  critical: {
    icon: AlertCircle,
    color: 'text-red-500',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/30',
    label: 'Critical',
  },
}

async function fetchSchedulerStatus(projectName: string): Promise<SchedulerStatus> {
  const response = await fetch(`/api/scheduler/${encodeURIComponent(projectName)}/status`)
  if (!response.ok) {
    throw new Error('Failed to fetch scheduler status')
  }
  return response.json()
}

export function UsageLevelIndicator({ projectName }: UsageLevelIndicatorProps) {
  const { data: status, isLoading, error } = useQuery({
    queryKey: ['scheduler-status', projectName],
    queryFn: () => fetchSchedulerStatus(projectName!),
    enabled: !!projectName,
    refetchInterval: 30000, // Refresh every 30 seconds
    retry: 1,
  })

  if (!projectName || isLoading || error || !status) {
    return null
  }

  const config = LEVEL_CONFIG[status.level]
  const Icon = config.icon
  const percentUsed = Math.round(status.overallPercentageUsed)

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <div
            className={`flex items-center gap-1.5 px-2 py-1 rounded-md border cursor-default transition-colors ${config.bgColor} ${config.borderColor}`}
          >
            <Icon size={14} className={config.color} />
            <span className={`text-xs font-medium ${config.color}`}>
              {percentUsed}%
            </span>
          </div>
        </TooltipTrigger>
        <TooltipContent side="bottom" className="max-w-xs">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Badge
                variant="outline"
                className={`${config.bgColor} ${config.color} border-0`}
              >
                {config.label}
              </Badge>
              <span className="text-xs text-muted-foreground">
                {status.session.messagesRemaining} messages remaining
              </span>
            </div>
            <p className="text-sm">{status.statusMessage}</p>
            <div className="text-xs text-muted-foreground space-y-0.5">
              <div>Messages: {status.session.messagesSent}/{status.session.messagesLimit}</div>
              <div>Context: {Math.round(status.session.contextPercentUsed)}% used</div>
            </div>
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

export default UsageLevelIndicator
