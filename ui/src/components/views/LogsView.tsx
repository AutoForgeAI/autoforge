/**
 * Logs View
 *
 * Full-page log viewer with sub-tabs for Agent and Dev Server logs.
 * Extracted from the log rendering logic previously in DebugLogViewer.
 * Supports auto-scroll, log-level colorization, and timestamp formatting.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { useAppContext } from '@/contexts/AppContext'
import { Trash2, Cpu, Server } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'

type LogTab = 'agent' | 'devserver'
type LogLevel = 'error' | 'warn' | 'debug' | 'info'

const TAB_STORAGE_KEY = 'autoforge-logs-tab'

/** Parse log level from line content. */
function getLogLevel(line: string): LogLevel {
  const lower = line.toLowerCase()
  if (lower.includes('error') || lower.includes('exception') || lower.includes('traceback')) {
    return 'error'
  }
  if (lower.includes('warn') || lower.includes('warning')) {
    return 'warn'
  }
  if (lower.includes('debug')) {
    return 'debug'
  }
  return 'info'
}

/** Map log level to a Tailwind text-color class. */
function getLogColor(level: LogLevel): string {
  switch (level) {
    case 'error':
      return 'text-red-500'
    case 'warn':
      return 'text-yellow-500'
    case 'debug':
      return 'text-blue-400'
    case 'info':
    default:
      return 'text-foreground'
  }
}

/** Format an ISO timestamp to HH:MM:SS for compact log display. */
function formatTimestamp(timestamp: string): string {
  try {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return ''
  }
}

export function LogsView() {
  const { wsState } = useAppContext()

  // Sub-tab state, persisted to localStorage
  const [activeLogTab, setActiveLogTab] = useState<LogTab>(() => {
    try {
      const stored = localStorage.getItem(TAB_STORAGE_KEY)
      return stored === 'devserver' ? 'devserver' : 'agent'
    } catch {
      return 'agent'
    }
  })

  // Auto-scroll tracking per tab
  const [autoScroll, setAutoScroll] = useState(true)
  const [devAutoScroll, setDevAutoScroll] = useState(true)

  const scrollRef = useRef<HTMLDivElement>(null)
  const devScrollRef = useRef<HTMLDivElement>(null)

  // Persist the active tab to localStorage
  const handleTabChange = useCallback((tab: LogTab) => {
    setActiveLogTab(tab)
    try {
      localStorage.setItem(TAB_STORAGE_KEY, tab)
    } catch {
      // localStorage not available
    }
  }, [])

  // Auto-scroll agent logs when new entries arrive
  useEffect(() => {
    if (autoScroll && scrollRef.current && activeLogTab === 'agent') {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [wsState.logs, autoScroll, activeLogTab])

  // Auto-scroll dev server logs when new entries arrive
  useEffect(() => {
    if (devAutoScroll && devScrollRef.current && activeLogTab === 'devserver') {
      devScrollRef.current.scrollTop = devScrollRef.current.scrollHeight
    }
  }, [wsState.devLogs, devAutoScroll, activeLogTab])

  // Detect whether the user has scrolled away from the bottom (agent tab)
  const handleAgentScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget
    const isAtBottom = el.scrollHeight - el.scrollTop <= el.clientHeight + 50
    setAutoScroll(isAtBottom)
  }

  // Detect whether the user has scrolled away from the bottom (devserver tab)
  const handleDevScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget
    const isAtBottom = el.scrollHeight - el.scrollTop <= el.clientHeight + 50
    setDevAutoScroll(isAtBottom)
  }

  // Clear handler dispatches to the correct log source
  const handleClear = () => {
    if (activeLogTab === 'agent') {
      wsState.clearLogs()
    } else {
      wsState.clearDevLogs()
    }
  }

  // Determine if auto-scroll is paused for the active tab
  const isScrollPaused = activeLogTab === 'agent' ? !autoScroll : !devAutoScroll

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
      {/* Tab header bar */}
      <div className="flex items-center gap-2 px-4 py-2 border-b border-border bg-card/50">
        <Button
          variant={activeLogTab === 'agent' ? 'secondary' : 'ghost'}
          size="sm"
          onClick={() => handleTabChange('agent')}
          className="h-7 text-xs font-mono gap-1.5"
        >
          <Cpu size={12} />
          Agent
          {wsState.logs.length > 0 && (
            <Badge variant="default" className="h-4 px-1.5 text-[10px]">
              {wsState.logs.length}
            </Badge>
          )}
        </Button>
        <Button
          variant={activeLogTab === 'devserver' ? 'secondary' : 'ghost'}
          size="sm"
          onClick={() => handleTabChange('devserver')}
          className="h-7 text-xs font-mono gap-1.5"
        >
          <Server size={12} />
          Dev Server
          {wsState.devLogs.length > 0 && (
            <Badge variant="default" className="h-4 px-1.5 text-[10px]">
              {wsState.devLogs.length}
            </Badge>
          )}
        </Button>

        {/* Spacer */}
        <div className="flex-1" />

        {/* Auto-scroll paused indicator */}
        {isScrollPaused && (
          <Badge variant="default" className="bg-yellow-500 text-yellow-950">
            Paused
          </Badge>
        )}

        {/* Clear logs button */}
        <Button
          variant="ghost"
          size="icon"
          onClick={handleClear}
          className="h-7 w-7"
          title="Clear logs"
        >
          <Trash2 size={14} className="text-muted-foreground" />
        </Button>
      </div>

      {/* Log content area */}
      {activeLogTab === 'agent' ? (
        <div
          ref={scrollRef}
          onScroll={handleAgentScroll}
          className="flex-1 overflow-y-auto p-3 font-mono text-sm"
        >
          {wsState.logs.length === 0 ? (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              No logs yet. Start the agent to see output.
            </div>
          ) : (
            <div className="space-y-0.5">
              {wsState.logs.map((log, index) => {
                const level = getLogLevel(log.line)
                const colorClass = getLogColor(level)
                const timestamp = formatTimestamp(log.timestamp)

                return (
                  <div
                    key={`${log.timestamp}-${index}`}
                    className="flex gap-2 hover:bg-muted px-1 py-0.5 rounded"
                  >
                    <span className="text-muted-foreground select-none shrink-0">
                      {timestamp}
                    </span>
                    <span className={`${colorClass} whitespace-pre-wrap break-all`}>
                      {log.line}
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      ) : (
        <div
          ref={devScrollRef}
          onScroll={handleDevScroll}
          className="flex-1 overflow-y-auto p-3 font-mono text-sm"
        >
          {wsState.devLogs.length === 0 ? (
            <div className="flex items-center justify-center h-full text-muted-foreground">
              No dev server logs yet.
            </div>
          ) : (
            <div className="space-y-0.5">
              {wsState.devLogs.map((log, index) => {
                const level = getLogLevel(log.line)
                const colorClass = getLogColor(level)
                const timestamp = formatTimestamp(log.timestamp)

                return (
                  <div
                    key={`${log.timestamp}-${index}`}
                    className="flex gap-2 hover:bg-muted px-1 py-0.5 rounded"
                  >
                    <span className="text-muted-foreground select-none shrink-0">
                      {timestamp}
                    </span>
                    <span className={`${colorClass} whitespace-pre-wrap break-all`}>
                      {log.line}
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
