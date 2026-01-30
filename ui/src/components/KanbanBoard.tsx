import { useMemo } from 'react'
import { KanbanColumn } from './KanbanColumn'
import type { Feature, FeatureListResponse, ActiveAgent } from '../lib/types'
import { Card, CardContent } from '@/components/ui/card'

interface KanbanBoardProps {
  features: FeatureListResponse | undefined
  onFeatureClick: (feature: Feature) => void
  onAddFeature?: () => void
  onExpandProject?: () => void
  activeAgents?: ActiveAgent[]
  onCreateSpec?: () => void
  hasSpec?: boolean
  fourColumnView?: boolean  // Show 4 columns: Pending, In Progress, Testing, Complete
}

export function KanbanBoard({
  features,
  onFeatureClick,
  onAddFeature,
  onExpandProject,
  activeAgents = [],
  onCreateSpec,
  hasSpec = true,
  fourColumnView = false
}: KanbanBoardProps) {
  const hasFeatures = features && (features.pending.length + features.in_progress.length + features.done.length) > 0

  // Combine all features for dependency status calculation
  const allFeatures = features
    ? [...features.pending, ...features.in_progress, ...features.done]
    : []

  // Split done features into testing vs complete for 4-column view
  const { testingFeatures, completeFeatures } = useMemo(() => {
    if (!features || !fourColumnView) {
      return { testingFeatures: [], completeFeatures: features?.done || [] }
    }

    // Get feature IDs that have active testing agents
    const testingFeatureIds = new Set(
      activeAgents
        .filter(agent => agent.agentType === 'testing')
        .map(agent => agent.featureId)
    )

    const testing: Feature[] = []
    const complete: Feature[] = []

    for (const feature of features.done) {
      if (testingFeatureIds.has(feature.id)) {
        testing.push(feature)
      } else {
        complete.push(feature)
      }
    }

    return { testingFeatures: testing, completeFeatures: complete }
  }, [features, activeAgents, fourColumnView])

  const columnCount = fourColumnView ? 4 : 3
  const columnTitles = fourColumnView
    ? ['Pending', 'In Progress', 'Testing', 'Complete']
    : ['Pending', 'In Progress', 'Done']

  if (!features) {
    return (
      <div className={`grid grid-cols-1 md:grid-cols-${columnCount} gap-6`}>
        {columnTitles.map(title => (
          <Card key={title} className="py-4">
            <CardContent className="p-4">
              <div className="h-8 bg-muted animate-pulse rounded mb-4" />
              <div className="space-y-3">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-24 bg-muted animate-pulse rounded" />
                ))}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    )
  }

  if (fourColumnView) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <KanbanColumn
          title="Pending"
          count={features.pending.length}
          features={features.pending}
          allFeatures={allFeatures}
          activeAgents={activeAgents}
          color="pending"
          onFeatureClick={onFeatureClick}
          onAddFeature={onAddFeature}
          onExpandProject={onExpandProject}
          showExpandButton={hasFeatures}
          onCreateSpec={onCreateSpec}
          showCreateSpec={!hasSpec && !hasFeatures}
        />
        <KanbanColumn
          title="In Progress"
          count={features.in_progress.length}
          features={features.in_progress}
          allFeatures={allFeatures}
          activeAgents={activeAgents}
          color="progress"
          onFeatureClick={onFeatureClick}
        />
        <KanbanColumn
          title="Testing"
          count={testingFeatures.length}
          features={testingFeatures}
          allFeatures={allFeatures}
          activeAgents={activeAgents}
          color="testing"
          onFeatureClick={onFeatureClick}
        />
        <KanbanColumn
          title="Complete"
          count={completeFeatures.length}
          features={completeFeatures}
          allFeatures={allFeatures}
          activeAgents={activeAgents}
          color="done"
          onFeatureClick={onFeatureClick}
        />
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      <KanbanColumn
        title="Pending"
        count={features.pending.length}
        features={features.pending}
        allFeatures={allFeatures}
        activeAgents={activeAgents}
        color="pending"
        onFeatureClick={onFeatureClick}
        onAddFeature={onAddFeature}
        onExpandProject={onExpandProject}
        showExpandButton={hasFeatures}
        onCreateSpec={onCreateSpec}
        showCreateSpec={!hasSpec && !hasFeatures}
      />
      <KanbanColumn
        title="In Progress"
        count={features.in_progress.length}
        features={features.in_progress}
        allFeatures={allFeatures}
        activeAgents={activeAgents}
        color="progress"
        onFeatureClick={onFeatureClick}
      />
      <KanbanColumn
        title="Done"
        count={features.done.length}
        features={features.done}
        allFeatures={allFeatures}
        activeAgents={activeAgents}
        color="done"
        onFeatureClick={onFeatureClick}
      />
    </div>
  )
}
