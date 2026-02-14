import { useMemo, useState, useEffect } from 'react'
import { Wifi, WifiOff, Brain, Sparkles } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import type { AgentStatus } from '../lib/types'

interface ProgressDashboardProps {
  passing: number
  total: number
  percentage: number
  isConnected: boolean
  logs?: Array<{ line: string; timestamp: string }>
  agentStatus?: AgentStatus
}

const IDLE_TIMEOUT = 30000

function isAgentThought(line: string): boolean {
  const trimmed = line.trim()
  if (/^\[Tool:/.test(trimmed)) return false
  if (/^\s*Input:\s*\{/.test(trimmed)) return false
  if (/^\[(Done|Error)\]/.test(trimmed)) return false
  if (/^Output:/.test(trimmed)) return false
  if (/^[[{]/.test(trimmed)) return false
  if (trimmed.length < 10) return false
  if (/^[A-Za-z]:\\/.test(trimmed)) return false
  if (/^\/[a-z]/.test(trimmed)) return false
  return true
}

function getLatestThought(logs: Array<{ line: string; timestamp: string }>): string | null {
  for (let i = logs.length - 1; i >= 0; i--) {
    if (isAgentThought(logs[i].line)) {
      return logs[i].line.trim()
    }
  }
  return null
}

export function ProgressDashboard({
  passing,
  total,
  percentage,
  isConnected,
  logs = [],
  agentStatus,
}: ProgressDashboardProps) {
  const thought = useMemo(() => getLatestThought(logs), [logs])
  const [displayedThought, setDisplayedThought] = useState<string | null>(null)
  const [textVisible, setTextVisible] = useState(true)

  const lastLogTimestamp = logs.length > 0
    ? new Date(logs[logs.length - 1].timestamp).getTime()
    : 0

  const showThought = useMemo(() => {
    if (!thought) return false
    if (agentStatus === 'running' || agentStatus === 'pausing') return true
    if (agentStatus === 'paused') {
      return Date.now() - lastLogTimestamp < IDLE_TIMEOUT
    }
    return false
  }, [thought, agentStatus, lastLogTimestamp])

  useEffect(() => {
    if (thought !== displayedThought && thought) {
      setTextVisible(false)
      const timeout = setTimeout(() => {
        setDisplayedThought(thought)
        setTextVisible(true)
      }, 150)
      return () => clearTimeout(timeout)
    }
  }, [thought, displayedThought])

  const isRunning = agentStatus === 'running'

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-0">
        <div className="flex items-center gap-3">
          <CardTitle className="text-xl uppercase tracking-wide">
            Progress
          </CardTitle>
          <Badge variant={isConnected ? 'default' : 'destructive'} className="gap-1">
            {isConnected ? (
              <>
                <Wifi size={14} />
                Live
              </>
            ) : (
              <>
                <WifiOff size={14} />
                Offline
              </>
            )}
          </Badge>
        </div>
        <div className="flex items-baseline gap-1">
          <span className="font-mono text-lg font-bold text-primary">
            {passing}
          </span>
          <span className="text-sm text-muted-foreground">/</span>
          <span className="font-mono text-lg font-bold">
            {total}
          </span>
        </div>
      </CardHeader>

      <CardContent className="pt-3 pb-3">
        <div className="flex items-center gap-4">
          {/* Progress Bar */}
          <div className="h-2.5 bg-muted rounded-full overflow-hidden flex-1">
            <div
              className="h-full bg-primary rounded-full transition-all duration-500 ease-out"
              style={{ width: `${percentage}%` }}
            />
          </div>
          {/* Percentage */}
          <span className="text-sm font-bold tabular-nums text-muted-foreground w-12 text-right">
            {percentage.toFixed(1)}%
          </span>
        </div>

        {/* Agent Thought */}
        <div
          className={`
            transition-all duration-300 ease-out overflow-hidden
            ${showThought && displayedThought ? 'opacity-100 max-h-10 mt-3' : 'opacity-0 max-h-0 mt-0'}
          `}
        >
          <div className="flex items-center gap-2">
            <div className="relative shrink-0">
              <Brain size={16} className="text-primary" strokeWidth={2.5} />
              {isRunning && (
                <Sparkles size={8} className="absolute -top-1 -right-1 text-yellow-500 animate-pulse" />
              )}
            </div>
            <p
              className="font-mono text-sm truncate text-muted-foreground transition-all duration-150 ease-out"
              style={{
                opacity: textVisible ? 1 : 0,
                transform: textVisible ? 'translateY(0)' : 'translateY(-4px)',
              }}
            >
              {displayedThought?.replace(/:$/, '')}
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
