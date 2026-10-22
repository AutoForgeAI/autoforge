/**
 * Feature Browser Preview
 *
 * Shows the live browser view of the agent currently working on a feature,
 * so testing can be watched from the feature detail modal instead of a
 * desktop browser window. Subscribes to screenshot streaming while mounted.
 */

import { useEffect } from 'react'
import { Monitor, Code, FlaskConical, ExternalLink } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { AGENT_MASCOTS } from '@/lib/types'
import type { ActiveAgent, BrowserScreenshot } from '@/lib/types'

interface FeatureBrowserPreviewProps {
  featureId: number
  activeAgents: ActiveAgent[]
  screenshots: Map<string, BrowserScreenshot>
  onSubscribe: () => void
  onUnsubscribe: () => void
  onOpenBrowsersView?: () => void
}

/** Agents (coding or testing) whose current batch includes the feature. */
function getAgentsForFeature(featureId: number, activeAgents: ActiveAgent[]): ActiveAgent[] {
  return activeAgents.filter(a =>
    a.featureId === featureId || (a.featureIds?.includes(featureId) ?? false)
  )
}

/** Latest screenshots belonging to the agents working on the feature. */
function getScreenshotsForFeature(
  featureId: number,
  activeAgents: ActiveAgent[],
  screenshots: Map<string, BrowserScreenshot>,
): BrowserScreenshot[] {
  // Browser sessions are keyed by the agent's primary feature, so a batched
  // feature is matched through the agent that owns the batch.
  const primaryIds = new Set<number>([featureId])
  for (const agent of getAgentsForFeature(featureId, activeAgents)) {
    primaryIds.add(agent.featureId)
  }
  return Array.from(screenshots.values()).filter(s => primaryIds.has(s.featureId))
}

export function FeatureBrowserPreview({
  featureId,
  activeAgents,
  screenshots,
  onSubscribe,
  onUnsubscribe,
  onOpenBrowsersView,
}: FeatureBrowserPreviewProps) {
  useEffect(() => {
    onSubscribe()
    return () => onUnsubscribe()
  }, [onSubscribe, onUnsubscribe])

  const featureScreenshots = getScreenshotsForFeature(featureId, activeAgents, screenshots)

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-sm uppercase tracking-wide text-muted-foreground flex items-center gap-2">
          <Monitor size={16} />
          Live Browser
        </h3>
        {onOpenBrowsersView && (
          <Button variant="ghost" size="sm" onClick={onOpenBrowsersView}>
            <ExternalLink size={14} />
            All browsers
          </Button>
        )}
      </div>

      {featureScreenshots.length === 0 ? (
        <div className="flex flex-col items-center justify-center gap-1 p-6 bg-muted rounded-lg text-muted-foreground">
          <Monitor size={20} />
          <span className="text-sm">No browser open for this feature yet</span>
          <span className="text-xs">The view appears here when the agent starts browser testing</span>
        </div>
      ) : (
        <div className="space-y-3">
          {featureScreenshots.map(screenshot => (
            <div
              key={screenshot.sessionName}
              className="border-2 border-border rounded-lg overflow-hidden bg-card"
            >
              <div className="flex items-center gap-2 px-2.5 py-1.5 bg-muted border-b border-border">
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
                <span className="ml-auto text-[10px] text-muted-foreground font-mono">
                  {new Date(screenshot.timestamp).toLocaleTimeString('en-US', {
                    hour12: false,
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit',
                  })}
                </span>
              </div>
              <img
                src={screenshot.imageDataUrl}
                alt={`Browser view - ${screenshot.featureName}`}
                className="w-full h-auto max-h-[50vh] object-contain object-top"
              />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
