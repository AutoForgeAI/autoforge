/**
 * Browser View Panel
 *
 * Displays live screenshots from each agent's browser session.
 * Subscribes to screenshot streaming on mount, unsubscribes on unmount.
 */

import { useEffect, useState } from 'react'
import { Monitor, X, Maximize2, Code, FlaskConical } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { AGENT_MASCOTS } from '@/lib/types'
import type { BrowserScreenshot } from '@/lib/types'

interface BrowserViewPanelProps {
  screenshots: Map<string, BrowserScreenshot>
  onSubscribe: () => void
  onUnsubscribe: () => void
}

export function BrowserViewPanel({ screenshots, onSubscribe, onUnsubscribe }: BrowserViewPanelProps) {
  const [expandedSession, setExpandedSession] = useState<string | null>(null)

  // Subscribe on mount, unsubscribe on unmount
  useEffect(() => {
    onSubscribe()
    return () => onUnsubscribe()
  }, [onSubscribe, onUnsubscribe])

  const screenshotList = Array.from(screenshots.values())

  if (screenshotList.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-2">
        <Monitor size={24} />
        <span className="text-sm">No active browser sessions</span>
        <span className="text-xs">Screenshots will appear when agents open browsers</span>
      </div>
    )
  }

  const expanded = expandedSession ? screenshots.get(expandedSession) : null

  return (
    <div className="h-full overflow-auto p-3">
      {/* Expanded overlay */}
      {expanded && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
          onClick={() => setExpandedSession(null)}
        >
          <div
            className="relative max-w-[90vw] max-h-[90vh] bg-card border-2 border-border rounded-lg overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between px-3 py-2 bg-muted border-b border-border">
              <div className="flex items-center gap-2">
                {expanded.agentType === 'coding' ? (
                  <Code size={14} className="text-blue-500" />
                ) : (
                  <FlaskConical size={14} className="text-purple-500" />
                )}
                <span className="font-mono text-sm font-bold">
                  {AGENT_MASCOTS[expanded.agentIndex % AGENT_MASCOTS.length]}
                </span>
                <Badge variant="outline" className="text-[10px] h-4">
                  {expanded.agentType}
                </Badge>
                <span className="text-xs text-muted-foreground truncate">
                  {expanded.featureName}
                </span>
              </div>
              <button
                onClick={() => setExpandedSession(null)}
                className="p-1 hover:bg-accent rounded transition-colors cursor-pointer"
              >
                <X size={16} />
              </button>
            </div>
            <img
              src={expanded.imageDataUrl}
              alt={`Browser view - ${expanded.featureName}`}
              className="max-w-full max-h-[calc(90vh-3rem)] object-contain"
            />
          </div>
        </div>
      )}

      {/* Screenshot grid — responsive 1/2/3 columns */}
      <div className="grid gap-3 grid-cols-1 md:grid-cols-2 xl:grid-cols-3">
        {screenshotList.map((screenshot) => (
          <div
            key={screenshot.sessionName}
            className="border-2 border-border rounded-lg overflow-hidden bg-card hover:border-foreground/30 transition-colors"
          >
            {/* Card header */}
            <div className="flex items-center justify-between px-2.5 py-1.5 bg-muted border-b border-border">
              <div className="flex items-center gap-2 min-w-0">
                {screenshot.agentType === 'coding' ? (
                  <Code size={12} className="text-blue-500 shrink-0" />
                ) : (
                  <FlaskConical size={12} className="text-purple-500 shrink-0" />
                )}
                <span className="font-mono text-xs font-bold">
                  {AGENT_MASCOTS[screenshot.agentIndex % AGENT_MASCOTS.length]}
                </span>
                <Badge variant="outline" className="text-[9px] h-3.5 px-1">
                  {screenshot.agentType}
                </Badge>
                <span className="text-[11px] text-muted-foreground truncate">
                  {screenshot.featureName}
                </span>
              </div>
              <button
                onClick={() => setExpandedSession(screenshot.sessionName)}
                className="p-0.5 hover:bg-accent rounded transition-colors cursor-pointer shrink-0"
                title="Expand"
              >
                <Maximize2 size={12} className="text-muted-foreground" />
              </button>
            </div>

            {/* Screenshot image — capped height for compact grid */}
            <div
              className="cursor-pointer overflow-hidden"
              onClick={() => setExpandedSession(screenshot.sessionName)}
            >
              <img
                src={screenshot.imageDataUrl}
                alt={`Browser - ${screenshot.featureName}`}
                className="w-full h-auto max-h-[280px] object-cover object-top"
              />
            </div>

            {/* Timestamp footer */}
            <div className="px-2.5 py-1 bg-muted border-t border-border">
              <span className="text-[10px] text-muted-foreground font-mono">
                {new Date(screenshot.timestamp).toLocaleTimeString('en-US', {
                  hour12: false,
                  hour: '2-digit',
                  minute: '2-digit',
                  second: '2-digit',
                })}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
