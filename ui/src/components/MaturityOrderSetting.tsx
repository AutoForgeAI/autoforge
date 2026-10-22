import { ArrowUp, ArrowDown } from 'lucide-react'
import type { Maturity } from '../lib/types'
import { DEFAULT_MATURITY_ORDER, MATURITY_LABELS } from '../lib/maturity'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'

interface MaturityOrderSettingProps {
  order?: Maturity[]
  disabled?: boolean
  onChange: (order: Maturity[]) => void
}

/** Reorderable list of maturity tags (first = picked up first by agents). */
export function MaturityOrderSetting({ order: currentOrder, disabled = false, onChange }: MaturityOrderSettingProps) {
  const order = currentOrder ?? DEFAULT_MATURITY_ORDER

  const move = (index: number, direction: -1 | 1) => {
    const target = index + direction
    if (disabled || target < 0 || target >= order.length) return
    const next = [...order]
    ;[next[index], next[target]] = [next[target], next[index]]
    onChange(next)
  }

  return (
    <div className="space-y-2">
      <Label className="font-medium">Maturity Priority</Label>
      <p className="text-sm text-muted-foreground">
        Order in which agents pick up build-ready (Pending) features by maturity tag.
        Unreviewed features go last. Applies the next time the agent starts.
      </p>
      <ol className="space-y-1" data-testid="maturity-order">
        {order.map((level, index) => (
          <li key={level} className="flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm">
            <span className="font-mono text-xs text-muted-foreground w-4">{index + 1}</span>
            <span className="flex-1">{MATURITY_LABELS[level]}</span>
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              onClick={() => move(index, -1)}
              disabled={disabled || index === 0}
              aria-label={`Move ${MATURITY_LABELS[level]} up`}
            >
              <ArrowUp size={14} />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              onClick={() => move(index, 1)}
              disabled={disabled || index === order.length - 1}
              aria-label={`Move ${MATURITY_LABELS[level]} down`}
            >
              <ArrowDown size={14} />
            </Button>
          </li>
        ))}
      </ol>
    </div>
  )
}
