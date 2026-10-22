import type { MaturityLevel } from '../lib/types'
import { MATURITY_META } from '../lib/maturity'
import { Badge } from '@/components/ui/badge'

interface MaturityBadgeProps {
  maturity?: MaturityLevel | null
}

/** Small badge showing a feature's spec-review maturity tag (renders nothing when untagged). */
export function MaturityBadge({ maturity }: MaturityBadgeProps) {
  if (!maturity || !(maturity in MATURITY_META)) return null
  const meta = MATURITY_META[maturity]
  const Icon = meta.icon
  return (
    <Badge variant="outline" className={meta.className} title={meta.description}>
      <Icon size={12} />
      {meta.label}
    </Badge>
  )
}
