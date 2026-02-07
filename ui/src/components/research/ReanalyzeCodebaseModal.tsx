/**
 * Reanalyze Codebase Modal Component
 *
 * A confirmation dialog for re-analyzing an existing project's codebase.
 * This is used when a project is already registered and the user wants
 * to update the research documentation after external changes.
 */

import { useState } from 'react'
import { Loader2, Microscope, RefreshCw, AlertCircle, FileText } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'

interface ReanalyzeCodebaseModalProps {
  isOpen: boolean
  projectName: string
  projectPath?: string
  onClose: () => void
  onStartAnalysis: () => void
}

export function ReanalyzeCodebaseModal({
  isOpen,
  projectName,
  projectPath,
  onClose,
  onStartAnalysis,
}: ReanalyzeCodebaseModalProps) {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Start the research analysis
  const handleStartAnalysis = async () => {
    setIsLoading(true)
    setError(null)

    try {
      // Call the API to start research analysis on existing project
      const response = await fetch(
        `/api/projects/${encodeURIComponent(projectName)}/agent/start-research`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({}),
        }
      )

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(errorData.detail || `HTTP ${response.status}`)
      }

      // Success - call the callback to navigate to progress view
      onStartAnalysis()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start analysis')
      setIsLoading(false)
    }
  }

  // Handle modal close
  const handleClose = () => {
    if (!isLoading) {
      setError(null)
      onClose()
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-100 dark:bg-emerald-900/30 rounded-lg">
              <Microscope size={24} className="text-emerald-600 dark:text-emerald-400" />
            </div>
            <div>
              <DialogTitle>Re-analyze Codebase</DialogTitle>
              <DialogDescription>
                Update research documentation for this project
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Project info */}
          <div className="p-3 bg-muted rounded-md">
            <p className="text-sm font-medium">{projectName}</p>
            {projectPath && (
              <p className="text-xs text-muted-foreground font-mono mt-1 truncate">
                {projectPath}
              </p>
            )}
          </div>

          {/* Explanation */}
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              The research agent will re-analyze the codebase and update the documentation
              in the <code className="px-1 py-0.5 bg-muted rounded text-xs">.planning/codebase/</code> directory.
            </p>

            <div className="text-sm text-muted-foreground bg-muted/50 rounded-md p-3">
              <p className="font-medium flex items-center gap-2 mb-2">
                <FileText size={16} />
                Documentation files updated:
              </p>
              <ul className="list-disc list-inside space-y-1 text-xs ml-1">
                <li><code>STACK.md</code> - Technology stack and dependencies</li>
                <li><code>ARCHITECTURE.md</code> - System architecture and patterns</li>
                <li><code>STRUCTURE.md</code> - Directory structure and organization</li>
                <li><code>CONVENTIONS.md</code> - Coding conventions and style</li>
                <li><code>INTEGRATIONS.md</code> - External integrations and APIs</li>
              </ul>
            </div>

            <p className="text-sm text-muted-foreground">
              Use this when the codebase has changed outside of AutoForge and you want
              the agent to understand the current state.
            </p>
          </div>

          {/* Error display */}
          {error && (
            <Alert variant="destructive">
              <AlertCircle size={16} />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </div>

        {/* Loading state */}
        {isLoading && (
          <div className="flex items-center justify-center gap-2 text-muted-foreground py-2">
            <Loader2 size={16} className="animate-spin" />
            <span>Starting analysis...</span>
          </div>
        )}

        <DialogFooter>
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={isLoading}
          >
            Cancel
          </Button>
          <Button
            onClick={handleStartAnalysis}
            disabled={isLoading}
            className="bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            {isLoading ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Starting...
              </>
            ) : (
              <>
                <RefreshCw size={16} />
                Start Analysis
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
