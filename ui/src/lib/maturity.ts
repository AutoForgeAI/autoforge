import { FlaskConical, Users, Rocket } from 'lucide-react'
import type { Feature, MaturityLevel } from './types'

export const MATURITY_LEVELS: MaturityLevel[] = ['alpha', 'limited_beta', 'beta']

export const MATURITY_META: Record<MaturityLevel, { label: string; description: string; className: string; icon: typeof Rocket }> = {
  alpha: {
    label: 'Alpha',
    description: 'Early/experimental, minimal scope, may ship behind a flag',
    className: 'bg-purple-500/15 text-purple-700 dark:text-purple-300 border-purple-500/40',
    icon: FlaskConical,
  },
  limited_beta: {
    label: 'Limited beta',
    description: 'Scoped rollout with tighter acceptance criteria and guardrails',
    className: 'bg-sky-500/15 text-sky-700 dark:text-sky-300 border-sky-500/40',
    icon: Users,
  },
  beta: {
    label: 'Beta',
    description: 'Broad readiness, stable requirements, strong quality bar',
    className: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/40',
    icon: Rocket,
  },
}

export type MaturityFilter = 'all' | 'untagged' | MaturityLevel

export function matchesMaturityFilter(feature: Feature, filter: MaturityFilter): boolean {
  if (filter === 'all') return true
  if (filter === 'untagged') return !feature.maturity
  return feature.maturity === filter
}
