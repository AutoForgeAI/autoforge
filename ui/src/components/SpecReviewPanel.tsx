import { useState } from 'react'
import { Archive, ArrowUpCircle, CheckCircle2, ClipboardCheck, Loader2, XCircle } from 'lucide-react'
import { useMoveFeatureToBacklog, usePromoteFeature, useReviewFeatureSpec } from '../hooks/useProjects'
import type { Feature, Maturity } from '../lib/types'
import { MATURITY_DESCRIPTIONS, MATURITY_LABELS, MATURITY_LEVELS } from '../lib/maturity'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'

interface SpecReviewPanelProps {
  feature: Feature
  projectName: string
  onError: (message: string | null) => void
}

/**
 * Spec Review step + Backlog/Pending controls for a single feature.
 *
 * - Assigns a maturity tag (alpha / limited beta / beta) with optional notes.
 * - Shows the ready checks that gate promotion from Backlog to Pending.
 * - Promotes (with an explicit human override when checks fail) or parks
 *   the feature in the Backlog.
 */
export function SpecReviewPanel({ feature, projectName, onError }: SpecReviewPanelProps) {
  const [maturity, setMaturity] = useState<Maturity | null>(feature.maturity ?? null)
  const [notes, setNotes] = useState(feature.spec_notes ?? '')
  const [confirmOverride, setConfirmOverride] = useState(false)

  const reviewSpec = useReviewFeatureSpec(projectName)
  const promote = usePromoteFeature(projectName)
  const moveToBacklog = useMoveFeatureToBacklog(projectName)

  const isDirty = maturity !== (feature.maturity ?? null) || notes !== (feature.spec_notes ?? '')
  const readiness = feature.readiness ?? []
  const isBusy = reviewSpec.isPending || promote.isPending || moveToBacklog.isPending

  const run = async (action: () => Promise<unknown>, fallback: string) => {
    onError(null)
    try {
      await action()
      return true
    } catch (err) {
      onError(err instanceof Error ? err.message : fallback)
      return false
    }
  }

  const handleSaveReview = () => {
    if (!maturity) return
    run(
      () => reviewSpec.mutateAsync({ featureId: feature.id, maturity, notes: notes.trim() || null }),
      'Failed to save spec review',
    )
  }

  const handlePromote = async (force: boolean) => {
    const ok = await run(
      () => promote.mutateAsync({ featureId: feature.id, force }),
      'Failed to promote feature',
    )
    if (ok) setConfirmOverride(false)
  }

  return (
    <div className="space-y-4 rounded-lg border p-4" data-testid="spec-review-panel">
      <h3 className="font-semibold text-sm uppercase tracking-wide text-muted-foreground flex items-center gap-2">
        <ClipboardCheck size={16} />
        Spec Review
      </h3>

      {/* Maturity tag */}
      <div className="space-y-2">
        <Label>Maturity tag</Label>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2" role="radiogroup" aria-label="Maturity tag">
          {MATURITY_LEVELS.map(level => (
            <Button
              key={level}
              type="button"
              role="radio"
              aria-checked={maturity === level}
              variant={maturity === level ? 'default' : 'outline'}
              onClick={() => setMaturity(level)}
              title={MATURITY_DESCRIPTIONS[level]}
              disabled={isBusy}
            >
              {MATURITY_LABELS[level]}
            </Button>
          ))}
        </div>
        <p className="text-xs text-muted-foreground">
          {maturity ? MATURITY_DESCRIPTIONS[maturity] : 'Required before the feature can move from Backlog to Pending.'}
        </p>
      </div>

      {/* Notes */}
      <div className="space-y-2">
        <Label htmlFor={`spec-notes-${feature.id}`}>Notes (optional)</Label>
        <Textarea
          id={`spec-notes-${feature.id}`}
          value={notes}
          onChange={e => setNotes(e.target.value)}
          placeholder="Rollout constraints, risks, must-not-break areas, dependencies..."
          maxLength={5000}
          disabled={isBusy}
        />
      </div>

      <Button onClick={handleSaveReview} disabled={!maturity || !isDirty || isBusy} size="sm">
        {reviewSpec.isPending ? <Loader2 size={16} className="animate-spin" /> : 'Save Review'}
      </Button>

      {/* Backlog: ready checks + promotion */}
      {feature.backlog ? (
        <div className="space-y-3 pt-2 border-t">
          <h4 className="font-semibold text-sm pt-2">Ready checks (Backlog → Pending)</h4>
          <ul className="space-y-1" data-testid="ready-checks">
            {readiness.map(check => (
              <li key={check.id} className="flex items-start gap-2 text-sm">
                {check.passed ? (
                  <CheckCircle2 size={16} className="text-primary shrink-0 mt-0.5" />
                ) : (
                  <XCircle size={16} className="text-destructive shrink-0 mt-0.5" />
                )}
                <span>
                  {check.label}
                  {!check.passed && check.detail && (
                    <span className="block text-xs text-muted-foreground">{check.detail}</span>
                  )}
                </span>
              </li>
            ))}
          </ul>

          {feature.ready ? (
            <Button onClick={() => handlePromote(false)} disabled={isBusy || isDirty} className="w-full">
              {promote.isPending ? <Loader2 size={16} className="animate-spin" /> : <><ArrowUpCircle size={16} /> Promote to Pending</>}
            </Button>
          ) : confirmOverride ? (
            <div className="space-y-2">
              <p className="text-sm text-destructive">
                Some ready checks fail. Promoting anyway puts this feature in the agent build queue as-is.
              </p>
              <div className="flex gap-2">
                <Button variant="destructive" onClick={() => handlePromote(true)} disabled={isBusy} className="flex-1">
                  {promote.isPending ? <Loader2 size={16} className="animate-spin" /> : 'Promote Anyway'}
                </Button>
                <Button variant="outline" onClick={() => setConfirmOverride(false)} disabled={isBusy} className="flex-1">
                  Cancel
                </Button>
              </div>
            </div>
          ) : (
            <Button variant="outline" onClick={() => setConfirmOverride(true)} disabled={isBusy || isDirty} className="w-full">
              <ArrowUpCircle size={16} /> Override checks and promote…
            </Button>
          )}
          {isDirty && (
            <p className="text-xs text-muted-foreground">Save the review before promoting.</p>
          )}
        </div>
      ) : !feature.in_progress && (
        <div className="pt-2 border-t">
          <Button
            variant="outline"
            onClick={() => run(() => moveToBacklog.mutateAsync(feature.id), 'Failed to move feature to backlog')}
            disabled={isBusy}
            className="w-full mt-2"
          >
            {moveToBacklog.isPending ? <Loader2 size={16} className="animate-spin" /> : <><Archive size={16} /> Move to Backlog</>}
          </Button>
          <p className="text-xs text-muted-foreground mt-1">
            Backlog items are excluded from the agent queue until promoted.
          </p>
        </div>
      )}
    </div>
  )
}
