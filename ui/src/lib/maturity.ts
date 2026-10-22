import type { Feature, FeatureListResponse, Maturity } from './types'

// Spec roadmapping maturity tags (mirrors api/roadmap.py)
export const MATURITY_LEVELS: Maturity[] = ['alpha', 'limited_beta', 'beta']
export const DEFAULT_MATURITY_ORDER: Maturity[] = ['beta', 'limited_beta', 'alpha']

export const MATURITY_LABELS: Record<Maturity, string> = {
  alpha: 'Alpha',
  limited_beta: 'Limited Beta',
  beta: 'Beta',
}

export const MATURITY_DESCRIPTIONS: Record<Maturity, string> = {
  alpha: 'Early/experimental. May ship behind a flag, minimal scope, higher tolerance for iteration.',
  limited_beta: 'Scoped rollout to a subset of users. Tighter acceptance criteria, explicit guardrails.',
  beta: 'Broader readiness. Stronger quality bar, stable requirements.',
}

export const MATURITY_BADGE_CLASSES: Record<Maturity, string> = {
  alpha: 'bg-purple-500 text-white',
  limited_beta: 'bg-blue-500 text-white',
  beta: 'bg-emerald-600 text-white',
}

// Filter value for the board: a maturity tag, untagged features, or everything
export type MaturityFilter = Maturity | 'untagged' | 'all'

export function matchesMaturityFilter(feature: Feature, filter: MaturityFilter): boolean {
  if (filter === 'all') return true
  if (filter === 'untagged') return !feature.maturity
  return feature.maturity === filter
}

/** All features in a list response, across every column. */
export function allFeaturesOf(features: FeatureListResponse | undefined): Feature[] {
  if (!features) return []
  return [
    ...(features.backlog ?? []),
    ...features.pending,
    ...features.in_progress,
    ...features.done,
    ...(features.needs_human_input ?? []),
  ]
}
