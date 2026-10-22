/**
 * Usage Card
 *
 * Shows the project's cumulative token usage and cost (as reported by the
 * Claude Agent SDK at the end of each agent session), with progress toward
 * the global per-project cost limit configured in Settings.
 */

import { useState } from 'react'
import { AlertTriangle, Coins, RotateCcw } from 'lucide-react'
import { useProjectUsage, useResetProjectUsage } from '../hooks/useProjects'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ConfirmDialog } from './ConfirmDialog'

interface UsageCardProps {
  projectName: string
}

const tokenFormatter = new Intl.NumberFormat(undefined, { notation: 'compact', maximumFractionDigits: 1 })

function formatTokens(n: number): string {
  return tokenFormatter.format(n)
}

function formatCost(n: number): string {
  return `$${n.toFixed(n > 0 && n < 1 ? 3 : 2)}`
}

export function UsageCard({ projectName }: UsageCardProps) {
  const { data: usage } = useProjectUsage(projectName)
  const resetUsage = useResetProjectUsage(projectName)
  const [confirmReset, setConfirmReset] = useState(false)

  if (!usage) return null

  const { totals, cost_limit_usd: limit, limit_reached: limitReached } = usage
  const limitPct = limit ? Math.min((totals.cost_usd / limit) * 100, 100) : 0
  const nearLimit = !limitReached && limit !== null && limitPct >= 80

  return (
    <Card>
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-0">
        <div className="flex items-center gap-3">
          <CardTitle className="text-xl uppercase tracking-wide flex items-center gap-2">
            <Coins size={18} />
            Usage
          </CardTitle>
          {limitReached && (
            <Badge variant="destructive" className="gap-1">
              <AlertTriangle size={14} />
              Limit reached
            </Badge>
          )}
        </div>
        <div className="flex items-baseline gap-1">
          <span className="font-mono text-lg font-bold text-primary" data-testid="usage-cost">
            {formatCost(totals.cost_usd)}
          </span>
          {limit !== null && (
            <>
              <span className="text-sm text-muted-foreground">/</span>
              <span className="font-mono text-lg font-bold">{formatCost(limit)}</span>
            </>
          )}
        </div>
      </CardHeader>

      <CardContent className="pt-3 pb-3 space-y-3">
        {limit !== null && (
          <div className="h-2.5 bg-muted rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ease-out ${
                limitReached ? 'bg-destructive' : nearLimit ? 'bg-yellow-500' : 'bg-primary'
              }`}
              style={{ width: `${limitPct}%` }}
            />
          </div>
        )}

        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-sm text-muted-foreground">
          <span>
            <span className="font-mono font-semibold text-foreground">{formatTokens(totals.input_tokens)}</span> in
          </span>
          <span>
            <span className="font-mono font-semibold text-foreground">{formatTokens(totals.output_tokens)}</span> out
          </span>
          <span title="Prompt cache reads / writes">
            <span className="font-mono font-semibold text-foreground">{formatTokens(totals.cache_read_tokens)}</span>
            {' / '}
            <span className="font-mono font-semibold text-foreground">{formatTokens(totals.cache_creation_tokens)}</span> cache
          </span>
          <span>
            <span className="font-mono font-semibold text-foreground">{totals.sessions}</span> session{totals.sessions === 1 ? '' : 's'}
          </span>
          {limit === null && <span className="italic">No cost limit set (Settings)</span>}
          {totals.sessions > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="ml-auto h-7 gap-1"
              onClick={() => setConfirmReset(true)}
              disabled={resetUsage.isPending}
              title="Clear recorded usage for this project"
            >
              <RotateCcw size={14} />
              Reset
            </Button>
          )}
        </div>

        {limitReached && (
          <p className="text-sm text-destructive">
            This project has reached its cost limit. New agent sessions won't start until you raise
            the limit in Settings or reset usage.
          </p>
        )}
      </CardContent>

      <ConfirmDialog
        isOpen={confirmReset}
        title="Reset usage?"
        message="This clears the recorded token usage and cost for this project and restarts its spend against the cost limit."
        confirmLabel="Reset"
        variant="danger"
        isLoading={resetUsage.isPending}
        onConfirm={() => resetUsage.mutate(undefined, { onSettled: () => setConfirmReset(false) })}
        onCancel={() => setConfirmReset(false)}
      />
    </Card>
  )
}
