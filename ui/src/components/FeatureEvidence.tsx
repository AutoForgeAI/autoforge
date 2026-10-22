import { useState } from 'react'
import { CheckCircle2, ChevronDown, ChevronRight, ClipboardCheck, ImageOff, Loader2, XCircle } from 'lucide-react'
import { useFeatureEvidence } from '../hooks/useProjects'
import { getFeatureEvidenceScreenshotUrl } from '../lib/api'
import type { TestEvidenceEntry } from '../lib/types'
import { Badge } from '@/components/ui/badge'

interface FeatureEvidenceProps {
  projectName: string
  featureId: number
  evidenceCount: number
}

function formatTimestamp(value: string | null): string | null {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function EvidenceScreenshot({ src, path }: { src: string; path: string }) {
  const [failed, setFailed] = useState(false)

  if (failed) {
    return (
      <div className="flex items-center gap-2 p-2 rounded-md border border-dashed text-xs text-muted-foreground">
        <ImageOff size={14} />
        <span className="font-mono break-all">{path}</span>
        <span>(file unavailable)</span>
      </div>
    )
  }

  return (
    <a href={src} target="_blank" rel="noopener noreferrer" title={path} className="block">
      <img
        src={src}
        alt={`Test screenshot ${path}`}
        loading="lazy"
        onError={() => setFailed(true)}
        className="max-h-48 w-auto rounded-md border hover:opacity-90"
      />
    </a>
  )
}

function EvidenceItem({
  entry,
  projectName,
  featureId,
  defaultOpen,
}: {
  entry: TestEvidenceEntry
  projectName: string
  featureId: number
  defaultOpen: boolean
}) {
  const [showLog, setShowLog] = useState(false)
  const passed = entry.result === 'pass'
  const timestamp = formatTimestamp(entry.recorded_at)

  return (
    <details open={defaultOpen} className="group p-3 bg-muted rounded-md text-sm">
      <summary className="flex items-center gap-2 cursor-pointer list-none">
        <ChevronRight size={14} className="shrink-0 transition-transform group-open:rotate-90" />
        {passed ? (
          <CheckCircle2 size={16} className="shrink-0 text-primary" />
        ) : (
          <XCircle size={16} className="shrink-0 text-destructive" />
        )}
        <span className={`font-medium ${passed ? 'text-primary' : 'text-destructive'}`}>
          {passed ? 'Passed' : 'Failed'}
        </span>
        {entry.agent_type && (
          <Badge variant="outline" className="text-xs capitalize">
            {entry.agent_type} agent
          </Badge>
        )}
        {timestamp && (
          <span className="ml-auto text-xs text-muted-foreground">{timestamp}</span>
        )}
      </summary>

      <div className="mt-3 space-y-3">
        {entry.summary && (
          <p className="whitespace-pre-wrap break-words">{entry.summary}</p>
        )}

        {entry.screenshots.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {entry.screenshots.map(path => (
              <EvidenceScreenshot
                key={path}
                path={path}
                src={getFeatureEvidenceScreenshotUrl(projectName, featureId, path)}
              />
            ))}
          </div>
        )}

        {entry.log && (
          <div>
            <button
              type="button"
              onClick={() => setShowLog(v => !v)}
              className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
            >
              {showLog ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
              {showLog ? 'Hide test log' : 'Show test log'}
            </button>
            {showLog && (
              <pre className="mt-2 p-3 max-h-64 overflow-auto rounded-md bg-background border text-xs font-mono whitespace-pre-wrap break-words">
                {entry.log}
              </pre>
            )}
          </div>
        )}
      </div>
    </details>
  )
}

export function FeatureEvidence({ projectName, featureId, evidenceCount }: FeatureEvidenceProps) {
  const { data, isLoading, error } = useFeatureEvidence(projectName, featureId, evidenceCount)

  if (evidenceCount <= 0) return null

  // Newest first so the latest verification is what reviewers see
  const entries = [...(data?.evidence ?? [])].reverse()

  return (
    <div>
      <h3 className="font-semibold mb-2 text-sm uppercase tracking-wide text-muted-foreground flex items-center gap-2">
        <ClipboardCheck size={16} />
        Test Evidence
      </h3>
      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 size={16} className="animate-spin" />
          Loading evidence...
        </div>
      ) : error ? (
        <p className="text-sm text-destructive">
          {error instanceof Error ? error.message : 'Failed to load test evidence'}
        </p>
      ) : (
        <div className="space-y-2">
          {entries.map((entry, index) => (
            <EvidenceItem
              key={`${entry.recorded_at ?? ''}-${index}`}
              entry={entry}
              projectName={projectName}
              featureId={featureId}
              defaultOpen={index === 0}
            />
          ))}
        </div>
      )}
    </div>
  )
}
