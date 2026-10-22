import { useState } from 'react'
import { Archive, ArrowRightCircle, CheckCircle2, ClipboardCheck, Loader2, XCircle } from 'lucide-react'
import { useFeatureReadiness, useMoveFeatureToBacklog, usePromoteFeature, useUpdateFeature } from '../hooks/useProjects'
import { MATURITY_LEVELS, MATURITY_META } from '../lib/maturity'
import type { Feature, MaturityLevel } from '../lib/types'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

interface SpecReviewPanelProps {
  feature: Feature
  projectName: string
  onError: (message: string | null) => void
  onPromoted?: () => void
}

/**
 * Spec review: assign a maturity tag + notes, and move a feature between
 * Backlog and Pending. Promotion is gated by the spec completeness checklist,
 * with an explicit human override.
 */
export function SpecReviewPanel({ feature, projectName, onError, onPromoted }: SpecReviewPanelProps) {
  const [maturity, setMaturity] = useState<MaturityLevel | null>(feature.maturity ?? null)
  const [notes, setNotes] = useState(feature.spec_notes ?? '')
  const [confirmForce, setConfirmForce] = useState(false)

  const updateFeature = useUpdateFeature(projectName)
  const promoteFeature = usePromoteFeature(projectName)
  const moveToBacklog = useMoveFeatureToBacklog(projectName)
  const readiness = useFeatureReadiness(projectName, feature.id, !!feature.backlog)

  const isDirty = maturity !== (feature.maturity ?? null) || notes.trim() !== (feature.spec_notes ?? '').trim()
  const busy = updateFeature.isPending || promoteFeature.isPending || moveToBacklog.isPending

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

  const handleSave = () =>
    run(
      () => updateFeature.mutateAsync({
        featureId: feature.id,
        update: { maturity, spec_notes: notes.trim() || null },
      }),
      'Failed to save spec review',
    )

  const handlePromote = async (force: boolean) => {
    // Save pending review edits first so the ready checks see them
    if (isDirty && !(await handleSave())) return
    const ok = await run(() => promoteFeature.mutateAsync({ featureId: feature.id, force }), 'Failed to promote feature')
    setConfirmForce(false)
    if (ok) onPromoted?.()
  }

  // Ready checks are evaluated server-side on saved data; reflect unsaved edits locally
  const checks = (readiness.data?.checks ?? []).map(c =>
    c.id === 'maturity' ? { ...c, passed: maturity !== null } : c
  )
  const ready = checks.length > 0 && checks.every(c => c.passed)

  return (
    <div className="space-y-4 rounded-lg border p-4">
      <h3 className="font-semibold text-sm uppercase tracking-wide text-muted-foreground flex items-center gap-2">
        <ClipboardCheck size={16} />
        Spec Review
      </h3>

      {/* Maturity tag */}
      <div className="space-y-2">
        <p className="text-sm font-medium">Maturity</p>
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Maturity tag">
          {MATURITY_LEVELS.map(level => {
            const meta = MATURITY_META[level]
            const Icon = meta.icon
            const selected = maturity === level
            return (
              <Button
                key={level}
                type="button"
                size="sm"
                variant={selected ? 'default' : 'outline'}
                role="radio"
                aria-checked={selected}
                title={meta.description}
                onClick={() => setMaturity(level)}
                disabled={busy}
              >
                <Icon size={14} />
                {meta.label}
              </Button>
            )
          })}
          <Button
            type="button"
            size="sm"
            variant={maturity === null ? 'secondary' : 'ghost'}
            role="radio"
            aria-checked={maturity === null}
            onClick={() => setMaturity(null)}
            disabled={busy}
          >
            Untagged
          </Button>
        </div>
        {maturity && <p className="text-xs text-muted-foreground">{MATURITY_META[maturity].description}</p>}
      </div>

      {/* Notes */}
      <div className="space-y-2">
        <label htmlFor={`spec-notes-${feature.id}`} className="text-sm font-medium">
          Notes <span className="text-muted-foreground font-normal">(rollout constraints, risks, must-not-break areas)</span>
        </label>
        <Textarea
          id={`spec-notes-${feature.id}`}
          value={notes}
          onChange={e => setNotes(e.target.value)}
          rows={3}
          maxLength={5000}
          disabled={busy}
        />
      </div>

      {isDirty && (
        <Button size="sm" onClick={handleSave} disabled={busy}>
          {updateFeature.isPending && <Loader2 size={14} className="animate-spin" />}
          Save review
        </Button>
      )}

      {/* Backlog -> Pending promotion */}
      {feature.backlog ? (
        <div className="space-y-3 border-t pt-4">
          <p className="text-sm font-medium">Ready checks</p>
          {readiness.isLoading ? (
            <Loader2 size={16} className="animate-spin text-muted-foreground" />
          ) : (
            <ul className="space-y-1">
              {checks.map(c => (
                <li key={c.id} className="flex items-center gap-2 text-sm">
                  {c.passed
                    ? <CheckCircle2 size={16} className="text-primary shrink-0" />
                    : <XCircle size={16} className="text-destructive shrink-0" />}
                  <span className={c.passed ? '' : 'text-destructive'}>{c.label}</span>
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => handlePromote(false)} disabled={busy || !ready}>
              {promoteFeature.isPending ? <Loader2 size={14} className="animate-spin" /> : <ArrowRightCircle size={14} />}
              Promote to Pending
            </Button>
            {!ready && !readiness.isLoading && (
              confirmForce ? (
                <>
                  <Button size="sm" variant="destructive" onClick={() => handlePromote(true)} disabled={busy}>
                    Yes, promote anyway
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setConfirmForce(false)} disabled={busy}>
                    Cancel
                  </Button>
                </>
              ) : (
                <Button size="sm" variant="outline" onClick={() => setConfirmForce(true)} disabled={busy}>
                  Override checks…
                </Button>
              )
            )}
          </div>
        </div>
      ) : !feature.in_progress && (
        <div className="border-t pt-4 flex items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground">
            Not ready after all? Backlog items are never picked up by agents.
          </p>
          <Button
            size="sm"
            variant="outline"
            onClick={() => run(() => moveToBacklog.mutateAsync(feature.id), 'Failed to move feature to backlog')}
            disabled={busy}
          >
            {moveToBacklog.isPending ? <Loader2 size={14} className="animate-spin" /> : <Archive size={14} />}
            Move to Backlog
          </Button>
        </div>
      )}
    </div>
  )
}
