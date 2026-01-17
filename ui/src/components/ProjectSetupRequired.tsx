import { useState } from 'react'
import { AlertTriangle, Sparkles, FileText, Copy, ExternalLink } from 'lucide-react'

interface ProjectSetupRequiredProps {
  projectName: string
  promptsDir?: string | null
  onCreateSpec: () => void
  onOpenSettings: () => void
  onDismiss?: () => void
}

export function ProjectSetupRequired({
  projectName,
  promptsDir,
  onCreateSpec,
  onOpenSettings,
  onDismiss,
}: ProjectSetupRequiredProps) {
  const [copied, setCopied] = useState(false)
  const path = promptsDir || 'prompts'

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(path)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // no-op
    }
  }

  return (
    <div className="neo-card p-6 border-4 border-[var(--color-neo-danger)] bg-[var(--color-neo-card)]">
      <div className="flex items-start gap-4">
        <div className="p-2 bg-[var(--color-neo-danger)] border-3 border-[var(--color-neo-border)] shadow-[2px_2px_0px_rgba(0,0,0,1)]">
          <AlertTriangle size={20} className="text-white" />
        </div>
        <div className="flex-1">
          <div className="font-display font-bold uppercase">Project setup required</div>
          <div className="text-sm text-[var(--color-neo-text-secondary)] mt-1">
            <span className="font-mono">{projectName}</span> needs a real <span className="font-mono">app_spec.txt</span>{' '}
            before agents can create features.
          </div>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="neo-card p-3">
          <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-2">Recommended</div>
          <button className="neo-btn neo-btn-primary w-full text-sm" onClick={onCreateSpec}>
            <Sparkles size={16} />
            Create spec with Claude
          </button>
          <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
            Guided chat that writes <span className="font-mono">prompts/app_spec.txt</span>.
          </div>
        </div>

        <div className="neo-card p-3">
          <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-2">Manual</div>
          <button className="neo-btn neo-btn-secondary w-full text-sm" onClick={onOpenSettings}>
            <FileText size={16} />
            Open Generate tab
          </button>
          <div className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
            Edit prompts or run GSD → spec from Settings.
          </div>
        </div>

        <div className="neo-card p-3">
          <div className="text-xs font-mono text-[var(--color-neo-text-secondary)] mb-2">Prompts path</div>
          <div className="text-xs font-mono break-all">{path}</div>
          <div className="flex items-center gap-2 mt-2">
            <button className="neo-btn neo-btn-secondary text-sm" onClick={handleCopy}>
              <Copy size={16} />
              {copied ? 'Copied' : 'Copy path'}
            </button>
            <button className="neo-btn neo-btn-secondary text-sm" onClick={onOpenSettings} title="Open settings">
              <ExternalLink size={16} />
              Settings
            </button>
          </div>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs text-[var(--color-neo-text-secondary)]">
          You can snooze this banner, but Expand stays locked until the spec is real.
        </div>
        {onDismiss && (
          <button className="neo-btn neo-btn-secondary text-sm" onClick={onDismiss}>
            Remind me tomorrow
          </button>
        )}
      </div>
    </div>
  )
}
