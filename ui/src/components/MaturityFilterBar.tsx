import { Filter } from 'lucide-react'
import type { Feature, FeatureListResponse } from '../lib/types'
import { MATURITY_LEVELS, MATURITY_META, matchesMaturityFilter, type MaturityFilter } from '../lib/maturity'
import { Button } from '@/components/ui/button'

interface MaturityFilterBarProps {
  features: FeatureListResponse
  value: MaturityFilter
  onChange: (value: MaturityFilter) => void
}

/**
 * Filter chips for maturity tags, with per-stage counts (e.g. Pending-beta)
 * so the build-ready mix is visible at a glance. Hidden until at least one
 * feature has been tagged during spec review.
 */
export function MaturityFilterBar({ features, value, onChange }: MaturityFilterBarProps) {
  const stages: { key: string; label: string; list: Feature[] }[] = [
    { key: 'backlog', label: 'Backlog', list: features.backlog || [] },
    { key: 'pending', label: 'Pending', list: features.pending },
    { key: 'in_progress', label: 'In Progress', list: features.in_progress },
    { key: 'needs_input', label: 'Needs Input', list: features.needs_human_input || [] },
    { key: 'done', label: 'Done', list: features.done },
  ]
  const all = stages.flatMap(s => s.list)

  if (!all.some(f => f.maturity) && value === 'all') return null

  const options: MaturityFilter[] = ['all', ...[...MATURITY_LEVELS].reverse(), 'untagged']

  const labelFor = (opt: MaturityFilter) =>
    opt === 'all' ? 'All' : opt === 'untagged' ? 'Untagged' : MATURITY_META[opt].label

  const breakdown = (opt: MaturityFilter) =>
    stages
      .map(s => `${s.label}: ${s.list.filter(f => matchesMaturityFilter(f, opt)).length}`)
      .join('\n')

  const pendingSummary = MATURITY_LEVELS.slice().reverse()
    .map(level => ({ level, n: features.pending.filter(f => f.maturity === level).length }))
    .filter(x => x.n > 0)

  return (
    <div className="flex flex-wrap items-center gap-2" role="toolbar" aria-label="Filter by maturity">
      <Filter size={16} className="text-muted-foreground" />
      {options.map(opt => {
        const count = all.filter(f => matchesMaturityFilter(f, opt)).length
        return (
          <Button
            key={opt}
            size="sm"
            variant={value === opt ? 'default' : 'outline'}
            onClick={() => onChange(opt)}
            title={breakdown(opt)}
            aria-pressed={value === opt}
          >
            {labelFor(opt)}
            <span className="font-mono text-xs opacity-70">{count}</span>
          </Button>
        )
      })}
      {pendingSummary.length > 0 && (
        <span className="text-xs text-muted-foreground ml-2">
          Pending: {pendingSummary.map(x => `${x.n} ${MATURITY_META[x.level].label.toLowerCase()}`).join(' · ')}
        </span>
      )}
    </div>
  )
}
