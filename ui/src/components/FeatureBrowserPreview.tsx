/**
 * Feature Browser Preview
 *
 * Shows the live (headless) browser of any agent currently working on or
 * testing a feature, embedded in the feature detail modal. Agents always run
 * Playwright headless, so this is how users watch tests without desktop
 * browser windows popping up over their work.
 */

import { useEffect } from 'react'
import { Monitor, Code, FlaskConical, ExternalLink } from 'lucide-react'
import { useAppContext } from '@/contexts/AppContext'
import { AGENT_MASCOTS } from '@/lib/types'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

interface FeatureBrowserPreviewProps {
  featureId: number
  onOpenBrowsersView: () => void
}

export function FeatureBrowserPreview({ featureId, onOpenBrowsersView }: FeatureBrowserPreviewProps) {
  const { wsState } = useAppContext()
  const { subscribeBrowserView, unsubscribeBrowserView, browserScreenshots, activeAgents } = wsState

  // Stream screenshots only while the modal is open
  useEffect(() => {
    subscribeBrowserView()
    return () => unsubscribeBrowserView()
  }, [subscribeBrowserView, unsubscribeBrowserView])

  // Batched agents report their primary feature in screenshots, so also match
  // agents whose batch includes this feature
  const workingAgents = activeAgents.filter(a => a.featureIds.includes(featureId))
  const screenshots = Array.from(browserScreenshots.values()).filter(s =>
    s.featureId === featureId ||
    workingAgents.some(a => a.agentIndex === s.agentIndex && a.agentType === s.agentType)
  )

  if (screenshots.length === 0) {
    // Nothing to show unless an agent is actually on this feature
    if (workingAgents.length === 0) return null
    return (
      <div>
        <h3 className="font-semibold mb-2 text-sm uppercase tracking-wide text-muted-foreground flex items-center gap-2">
          <Monitor size={16} />
          Live Browser
        </h3>
        <div className="flex items-center gap-2 p-3 bg-muted rounded-md text-sm text-muted-foreground">
          <Monitor size={16} />
          The browser view will appear here once the agent opens a browser.
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-sm uppercase tracking-wide text-muted-foreground flex items-center gap-2">
          <Monitor size={16} />
          Live Browser
        </h3>
        <Button variant="ghost" size="sm" onClick={onOpenBrowsersView}>
          <ExternalLink size={14} />
          All browsers
        </Button>
      </div>
      <div className="space-y-3">
        {screenshots.map(screenshot => (
          <div
            key={screenshot.sessionName}
            className="border-2 border-border rounded-lg overflow-hidden bg-card"
            data-testid="feature-browser-preview"
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
              alt={`Live browser - ${screenshot.featureName}`}
              className="w-full h-auto"
            />
          </div>
        ))}
      </div>
    </div>
  )
}
