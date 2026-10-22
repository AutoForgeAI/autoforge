import type { Maturity } from '../lib/types'
import { MATURITY_BADGE_CLASSES, MATURITY_DESCRIPTIONS, MATURITY_LABELS } from '../lib/maturity'
import { Badge } from '@/components/ui/badge'

interface MaturityBadgeProps {
  maturity?: Maturity | null
  // Show an "Unreviewed" outline badge when no tag is set
  showUnreviewed?: boolean
}

export function MaturityBadge({ maturity, showUnreviewed = false }: MaturityBadgeProps) {
  if (!maturity) {
    if (!showUnreviewed) return null
    return (
      <Badge variant="outline" className="text-muted-foreground" title="No spec review yet">
        Unreviewed
      </Badge>
    )
  }

  return (
    <Badge
      className={MATURITY_BADGE_CLASSES[maturity]}
      title={MATURITY_DESCRIPTIONS[maturity]}
      data-testid="maturity-badge"
    >
      {MATURITY_LABELS[maturity]}
    </Badge>
  )
}
