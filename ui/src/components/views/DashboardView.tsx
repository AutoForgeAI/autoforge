/**
 * Dashboard View
 *
 * The command center: shows project progress and agent mission control.
 * The kanban board is a separate view accessible from the sidebar.
 */

import { useAppContext } from '@/contexts/AppContext'
import { ProgressDashboard } from '../ProgressDashboard'
import { AgentMissionControl } from '../AgentMissionControl'
import { Loader2 } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'

export function DashboardView() {
  const {
    progress,
    wsState,
    features,
  } = useAppContext()

  // Determine whether the agent is initializing features: the feature lists
  // are all empty, yet the agent is running (reading the spec and creating them).
  const isInitializingFeatures =
    features &&
    features.pending.length === 0 &&
    features.in_progress.length === 0 &&
    features.done.length === 0 &&
    (features.needs_human_input?.length || 0) === 0 &&
    wsState.agentStatus === 'running'

  return (
    <div className="overflow-y-auto flex-1 p-6 space-y-6">
      {/* Progress overview */}
      <ProgressDashboard
        passing={progress.passing}
        total={progress.total}
        percentage={progress.percentage}
        isConnected={wsState.isConnected}
        logs={wsState.activeAgents.length === 0 ? wsState.logs : undefined}
        agentStatus={wsState.activeAgents.length === 0 ? wsState.agentStatus : undefined}
      />

      {/* Agent Mission Control - orchestrator status and active agents */}
      <AgentMissionControl
        agents={wsState.activeAgents}
        orchestratorStatus={wsState.orchestratorStatus}
        recentActivity={wsState.recentActivity}
        getAgentLogs={wsState.getAgentLogs}
        browserScreenshots={wsState.browserScreenshots}
      />

      {/* Initializing Features - shown when agent is running but no features exist yet */}
      {isInitializingFeatures && (
        <Card className="p-8 text-center">
          <CardContent className="p-0">
            <Loader2 size={32} className="animate-spin mx-auto mb-4 text-primary" />
            <h3 className="font-display font-bold text-xl mb-2">
              Initializing Features...
            </h3>
            <p className="text-muted-foreground">
              The agent is reading your spec and creating features. This may take a moment.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
