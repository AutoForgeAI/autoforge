import { useState } from 'react'
import { ClipboardCheck, ImageOff, XCircle } from 'lucide-react'
import type { TestEvidence } from '../lib/types'
import { getEvidenceScreenshotUrl } from '../lib/api'
import { Badge } from '@/components/ui/badge'

interface TestEvidencePanelProps {
  evidence: TestEvidence
  projectName: string
  featureId: number
}

function EvidenceScreenshot({ src, path }: { src: string; path: string }) {
  const [failed, setFailed] = useState(false)

  if (failed) {
    return (
      <div className="flex items-center gap-2 p-3 bg-muted rounded-md text-xs text-muted-foreground">
        <ImageOff size={14} className="shrink-0" />
        <span className="truncate font-mono" title={path}>{path}</span>
      </div>
    )
  }

  return (
    <a
      href={src}
      target="_blank"
      rel="noopener noreferrer"
      className="block rounded-md border overflow-hidden hover:border-primary transition-colors"
      title={path}
    >
      <img
        src={src}
        alt={`Screenshot: ${path}`}
        loading="lazy"
        className="w-full h-32 object-cover object-top bg-muted"
        onError={() => setFailed(true)}
      />
      <div className="px-2 py-1 text-[10px] font-mono text-muted-foreground truncate">{path}</div>
    </a>
  )
}

export function TestEvidencePanel({ evidence, projectName, featureId }: TestEvidencePanelProps) {
  const isPassing = evidence.result === 'passing'
  const recordedAt = evidence.recorded_at ? new Date(evidence.recorded_at) : null
  const testLog = evidence.test_log ?? []
  const screenshots = evidence.screenshots ?? []

  return (
    <div>
      <h3 className="font-semibold mb-2 text-sm uppercase tracking-wide text-muted-foreground flex items-center gap-2">
        <ClipboardCheck size={16} />
        Test Evidence
      </h3>

      <div className="space-y-4 p-4 bg-muted/50 rounded-lg border">
        <div className="flex flex-wrap items-center gap-2">
          {isPassing ? (
            <Badge className="bg-primary text-primary-foreground">Verified passing</Badge>
          ) : (
            <Badge variant="destructive" className="gap-1">
              <XCircle size={12} />
              Regression found
            </Badge>
          )}
          {recordedAt && !isNaN(recordedAt.getTime()) && (
            <span className="text-xs text-muted-foreground">
              Recorded {recordedAt.toLocaleString()}
            </span>
          )}
        </div>

        {evidence.summary && (
          <div>
            <h4 className="font-semibold text-xs uppercase tracking-wide text-muted-foreground mb-1">Findings</h4>
            <p className="text-sm whitespace-pre-wrap">{evidence.summary}</p>
          </div>
        )}

        {testLog.length > 0 && (
          <div>
            <h4 className="font-semibold text-xs uppercase tracking-wide text-muted-foreground mb-1">Test Log</h4>
            <ol className="list-decimal list-inside space-y-1">
              {testLog.map((entry, index) => (
                <li key={index} className="text-sm whitespace-pre-wrap">
                  {entry}
                </li>
              ))}
            </ol>
          </div>
        )}

        {screenshots.length > 0 && (
          <div>
            <h4 className="font-semibold text-xs uppercase tracking-wide text-muted-foreground mb-1">
              Screenshots ({screenshots.length})
            </h4>
            <div className="grid grid-cols-2 gap-2">
              {screenshots.map((path, index) => (
                <EvidenceScreenshot
                  key={`${index}-${path}`}
                  path={path}
                  src={getEvidenceScreenshotUrl(projectName, featureId, index, evidence.recorded_at)}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
