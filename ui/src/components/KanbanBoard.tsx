import { useState } from 'react'
import { KanbanColumn } from './KanbanColumn'
import type { Feature, FeatureListResponse, ActiveAgent } from '../lib/types'
import {
  MATURITY_LABELS,
  MATURITY_LEVELS,
  allFeaturesOf,
  matchesMaturityFilter,
  type MaturityFilter,
} from '../lib/maturity'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'

interface KanbanBoardProps {
  features: FeatureListResponse | undefined
  onFeatureClick: (feature: Feature) => void
  onAddFeature?: () => void
  onExpandProject?: () => void
  activeAgents?: ActiveAgent[]
  onCreateSpec?: () => void
  hasSpec?: boolean
}

const FILTER_OPTIONS: { value: MaturityFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  ...[...MATURITY_LEVELS].reverse().map(m => ({ value: m as MaturityFilter, label: MATURITY_LABELS[m] })),
  { value: 'untagged', label: 'Unreviewed' },
]

export function KanbanBoard({ features, onFeatureClick, onAddFeature, onExpandProject, activeAgents = [], onCreateSpec, hasSpec = true }: KanbanBoardProps) {
  const [maturityFilter, setMaturityFilter] = useState<MaturityFilter>('all')

  // Combine all features for dependency status calculation (unfiltered)
  const allFeatures = allFeaturesOf(features)
  const hasFeatures = allFeatures.length > 0

  const needsInputCount = features?.needs_human_input?.length || 0
  const showNeedsInput = needsInputCount > 0

  if (!features) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {['Backlog', 'Pending', 'In Progress', 'Done'].map(title => (
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

  const filter = (list: Feature[] | undefined) =>
    (list ?? []).filter(f => matchesMaturityFilter(f, maturityFilter))

  const backlog = filter(features.backlog)
  const pending = filter(features.pending)
  const inProgress = filter(features.in_progress)
  const needsInput = filter(features.needs_human_input)
  const done = filter(features.done)

  // Build queue breakdown: Pending features by maturity tag
  const pendingByMaturity = (value: MaturityFilter) =>
    features.pending.filter(f => matchesMaturityFilter(f, value)).length

  return (
    <div className="space-y-4">
      {hasFeatures && (
        <div className="flex flex-wrap items-center gap-2" data-testid="maturity-filter">
          <span className="text-sm font-medium text-muted-foreground">Maturity:</span>
          {FILTER_OPTIONS.map(opt => {
            const count = opt.value === 'all'
              ? allFeatures.length
              : allFeatures.filter(f => matchesMaturityFilter(f, opt.value)).length
            return (
              <Button
                key={opt.value}
                size="sm"
                variant={maturityFilter === opt.value ? 'default' : 'outline'}
                onClick={() => setMaturityFilter(opt.value)}
                aria-pressed={maturityFilter === opt.value}
              >
                {opt.label}
                <span className="font-mono text-xs opacity-70">{count}</span>
              </Button>
            )
          })}
          <span className="text-xs text-muted-foreground ml-auto" title="Build-ready (Pending) features by maturity tag">
            Build queue:{' '}
            {FILTER_OPTIONS.filter(o => o.value !== 'all')
              .map(o => `${o.label} ${pendingByMaturity(o.value)}`)
              .join(' · ')}
          </span>
        </div>
      )}

      <div className={`grid grid-cols-1 md:grid-cols-2 ${showNeedsInput ? 'xl:grid-cols-5' : 'lg:grid-cols-4'} gap-6`}>
        <KanbanColumn
          title="Backlog"
          count={backlog.length}
          features={backlog}
          allFeatures={allFeatures}
          activeAgents={activeAgents}
          color="backlog"
          onFeatureClick={onFeatureClick}
          emptyMessage="No backlog. Park not-ready work here; agents never pick it up."
        />
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
