import { useState } from 'react'
import { KanbanColumn } from './KanbanColumn'
import { MaturityFilterBar } from './MaturityFilterBar'
import { matchesMaturityFilter, type MaturityFilter } from '../lib/maturity'
import type { Feature, FeatureListResponse, ActiveAgent } from '../lib/types'
import { Card, CardContent } from '@/components/ui/card'

// Static class names so Tailwind can see them
const gridCols: Record<number, string> = {
  3: 'md:grid-cols-3',
  4: 'md:grid-cols-2 lg:grid-cols-4',
  5: 'md:grid-cols-2 lg:grid-cols-5',
}

interface KanbanBoardProps {
  features: FeatureListResponse | undefined
  onFeatureClick: (feature: Feature) => void
  onAddFeature?: () => void
  onExpandProject?: () => void
  activeAgents?: ActiveAgent[]
  onCreateSpec?: () => void
  hasSpec?: boolean
}

export function KanbanBoard({ features, onFeatureClick, onAddFeature, onExpandProject, activeAgents = [], onCreateSpec, hasSpec = true }: KanbanBoardProps) {
  const [maturityFilter, setMaturityFilter] = useState<MaturityFilter>('all')

  const backlogFeatures = features?.backlog || []
  const hasFeatures = features && (features.pending.length + features.in_progress.length + features.done.length + (features.needs_human_input?.length || 0) + backlogFeatures.length) > 0

  // Combine all features for dependency status calculation
  const allFeatures = features
    ? [...backlogFeatures, ...features.pending, ...features.in_progress, ...features.done, ...(features.needs_human_input || [])]
    : []

  const filter = (list: Feature[]) => list.filter(f => matchesMaturityFilter(f, maturityFilter))

  const needsInputCount = features?.needs_human_input?.length || 0
  const showNeedsInput = needsInputCount > 0
  // Backlog column only appears once something has been put in the backlog
  const showBacklog = backlogFeatures.length > 0
  const columnCount = 3 + (showNeedsInput ? 1 : 0) + (showBacklog ? 1 : 0)

  if (!features) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {['Pending', 'In Progress', 'Done'].map(title => (
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

  const pending = filter(features.pending)
  const inProgress = filter(features.in_progress)
  const needsInput = filter(features.needs_human_input || [])
  const done = filter(features.done)
  const backlog = filter(backlogFeatures)

  return (
    <div className="space-y-4">
      <MaturityFilterBar features={features} value={maturityFilter} onChange={setMaturityFilter} />
      <div className={`grid grid-cols-1 ${gridCols[columnCount]} gap-6`}>
        {showBacklog && (
          <KanbanColumn
            title="Backlog"
            subtitle="Not ready - agents won't pick these up"
            count={backlog.length}
            features={backlog}
            allFeatures={allFeatures}
            activeAgents={activeAgents}
            color="backlog"
            onFeatureClick={onFeatureClick}
          />
        )}
        <KanbanColumn
          title="Pending"
          count={pending.length}
          features={pending}
          allFeatures={allFeatures}
          activeAgents={activeAgents}
          color="pending"
          onFeatureClick={onFeatureClick}
          onAddFeature={onAddFeature}
          onExpandProject={onExpandProject}
          showExpandButton={hasFeatures && hasSpec}
          onCreateSpec={onCreateSpec}
          showCreateSpec={!hasSpec && !hasFeatures}
        />
        <KanbanColumn
          title="In Progress"
          count={inProgress.length}
          features={inProgress}
          allFeatures={allFeatures}
          activeAgents={activeAgents}
          color="progress"
          onFeatureClick={onFeatureClick}
        />
        {showNeedsInput && (
          <KanbanColumn
            title="Needs Input"
            count={needsInput.length}
            features={needsInput}
            allFeatures={allFeatures}
            activeAgents={activeAgents}
            color="human_input"
            onFeatureClick={onFeatureClick}
          />
        )}
        <KanbanColumn
          title="Done"
          count={done.length}
          features={done}
          allFeatures={allFeatures}
          activeAgents={activeAgents}
          color="done"
          onFeatureClick={onFeatureClick}
        />
      </div>
    </div>
  )
}
