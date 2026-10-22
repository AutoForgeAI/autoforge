import { useState } from 'react'
import { Check, Copy, Loader2, ShieldAlert, Trash2 } from 'lucide-react'
import { useClearDeniedCommands, useDeniedCommands } from '../hooks/useProjects'
import type { DeniedCommandKind, DeniedCommandSummary } from '../lib/types'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Alert, AlertDescription } from '@/components/ui/alert'

interface DeniedCommandsDialogProps {
  isOpen: boolean
  projectName: string
  onClose: () => void
}

const KIND_LABELS: Record<DeniedCommandKind, { label: string; hint: string }> = {
  not_allowed: { label: 'Not allowed', hint: 'Can be added to allowed_commands.yaml' },
  blocklisted: { label: 'Blocklisted', hint: 'Hardcoded or org-level blocklist; cannot be allowed per project' },
  validation: { label: 'Invalid args', hint: 'Command is allowed but its arguments failed extra validation' },
  parse_error: { label: 'Unparseable', hint: 'The command string could not be parsed safely' },
}

/** Commands that could be unblocked by adding them to the project allowlist. */
function allowableCommands(commands: DeniedCommandSummary[]): DeniedCommandSummary[] {
  return commands.filter(c => c.kind === 'not_allowed' && c.command && !c.currently_allowed)
}

function buildAllowlistYaml(commands: DeniedCommandSummary[]): string {
  const lines = ['version: 1', 'commands:']
  for (const c of commands) {
    const name = /^[\w./*-]+$/.test(c.command) ? c.command : JSON.stringify(c.command)
    lines.push(`  - name: ${name}`)
    lines.push(`    description: Denied ${c.count}x during agent runs`)
  }
  return lines.join('\n') + '\n'
}

function formatTimestamp(ts: string): string {
  const date = new Date(ts)
  return isNaN(date.getTime()) ? ts : date.toLocaleString()
}

/**
 * Lists Bash commands the agent tried to run but were rejected by the
 * security hook, so the user can decide which ones to add to the project's
 * .autoforge/allowed_commands.yaml.
 */
export function DeniedCommandsDialog({ isOpen, projectName, onClose }: DeniedCommandsDialogProps) {
  const { data, isLoading, isError, error } = useDeniedCommands(isOpen ? projectName : null)
  const clearDenied = useClearDeniedCommands(projectName)
  const [copied, setCopied] = useState(false)

  const commands = data?.commands ?? []
  const allowable = allowableCommands(commands)

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(buildAllowlistYaml(allowable))
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // Clipboard unavailable (e.g. insecure context) - nothing else to do
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldAlert size={20} />
            Denied Commands
          </DialogTitle>
          <DialogDescription>
            Bash commands the agent tried to run in <span className="font-semibold">{projectName}</span> that
            were blocked by the security allowlist.
          </DialogDescription>
        </DialogHeader>

        <div className="max-h-[60vh] overflow-y-auto space-y-2 py-2">
          {isLoading && (
            <div className="flex items-center justify-center py-8 text-muted-foreground">
              <Loader2 className="animate-spin mr-2" size={16} />
              Loading...
            </div>
          )}

          {isError && (
            <Alert variant="destructive">
              <AlertDescription>
                {error instanceof Error ? error.message : 'Failed to load denied commands.'}
              </AlertDescription>
            </Alert>
          )}

          {!isLoading && !isError && commands.length === 0 && (
            <div className="py-8 text-center text-sm text-muted-foreground">
              No commands have been denied yet.
            </div>
          )}

          {commands.map(c => (
            <div
              key={`${c.kind}:${c.command}`}
              className="rounded-lg border-2 border-border p-3 space-y-1"
            >
              <div className="flex flex-wrap items-center gap-2">
                <code className="font-mono font-bold text-sm">{c.command || '(unparseable)'}</code>
                <Badge variant="secondary" title={KIND_LABELS[c.kind]?.hint}>
                  {KIND_LABELS[c.kind]?.label ?? c.kind}
                </Badge>
                {c.currently_allowed && (
                  <Badge className="bg-green-600 text-white">Now allowed</Badge>
                )}
                <div className="flex-1" />
                <span className="text-xs text-muted-foreground">
                  {c.count}x · last {formatTimestamp(c.last_seen)}
                </span>
              </div>
              <pre className="text-xs font-mono bg-muted/50 rounded p-2 whitespace-pre-wrap break-all max-h-24 overflow-y-auto">
                {c.last_full_command}
              </pre>
            </div>
          ))}
        </div>

        {allowable.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Copy the allowlist snippet and merge it into{' '}
            <code className="font-mono">.autoforge/allowed_commands.yaml</code> in the project folder.
            Review each command before allowing it.
          </p>
        )}

        {clearDenied.isError && (
          <Alert variant="destructive">
            <AlertDescription>
              {clearDenied.error instanceof Error ? clearDenied.error.message : 'Failed to clear log.'}
            </AlertDescription>
          </Alert>
        )}

        <DialogFooter className="gap-2">
          <Button
            variant="outline"
            onClick={() => clearDenied.mutate()}
            disabled={commands.length === 0 || clearDenied.isPending}
          >
            {clearDenied.isPending ? <Loader2 className="animate-spin" size={16} /> : <Trash2 size={16} />}
            Clear
          </Button>
          <Button onClick={handleCopy} disabled={allowable.length === 0}>
            {copied ? <Check size={16} /> : <Copy size={16} />}
            {copied ? 'Copied' : 'Copy allowlist YAML'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
