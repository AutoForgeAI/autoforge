/**
 * Analyze Codebase Modal Component
 *
 * Modal for selecting an existing codebase folder for research analysis.
 * Uses the FolderBrowser component to navigate the filesystem and
 * starts the research agent to analyze the selected codebase.
 */

import { useState, useEffect } from 'react'
import { Folder, Loader2, Search, AlertCircle } from 'lucide-react'
import { FolderBrowser } from '../FolderBrowser'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'

interface AnalyzeCodebaseModalProps {
  isOpen: boolean
  onClose: () => void
  onStartAnalysis: (projectName: string, projectDir: string) => void
}

type Step = 'folder' | 'confirm'

/**
 * Derives a project name from a folder path.
 * Takes the last segment of the path and sanitizes it for use as a project name.
 */
function deriveProjectName(folderPath: string): string {
  // Get the last segment of the path
  const segments = folderPath.split('/').filter(Boolean)
  const lastSegment = segments[segments.length - 1] || 'project'

  // Sanitize: only allow alphanumeric, hyphens, and underscores
  // Replace spaces and other chars with hyphens
  const sanitized = lastSegment
    .toLowerCase()
    .replace(/[^a-z0-9_-]/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '')

  return sanitized || 'project'
}

/**
 * Validates that a project name is valid.
 * Must be 1-50 chars, alphanumeric with hyphens and underscores.
 */
function isValidProjectName(name: string): boolean {
  return /^[a-zA-Z0-9_-]{1,50}$/.test(name)
}

export function AnalyzeCodebaseModal({
  isOpen,
  onClose,
  onStartAnalysis,
}: AnalyzeCodebaseModalProps) {
  const [step, setStep] = useState<Step>('folder')
  const [selectedPath, setSelectedPath] = useState<string | null>(null)
  const [projectName, setProjectName] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Reset state when modal opens/closes
  useEffect(() => {
    if (isOpen) {
      setStep('folder')
      setSelectedPath(null)
      setProjectName('')
      setError(null)
      setIsLoading(false)
    }
  }, [isOpen])

  // Handle folder selection from FolderBrowser
  const handleFolderSelect = (path: string) => {
    setSelectedPath(path)
    setProjectName(deriveProjectName(path))
    setError(null)
    setStep('confirm')
  }

  // Handle cancel from folder browser
  const handleFolderCancel = () => {
    onClose()
  }

  // Handle back from confirm step
  const handleBack = () => {
    setStep('folder')
    setError(null)
  }

  // Start the research analysis
  const handleStartAnalysis = async () => {
    if (!selectedPath) {
      setError('Please select a folder')
      return
    }

    const trimmedName = projectName.trim()
    if (!trimmedName) {
      setError('Please enter a project name')
      return
    }

    if (!isValidProjectName(trimmedName)) {
      setError('Project name can only contain letters, numbers, hyphens, and underscores (max 50 chars)')
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      // Call the API to start research analysis
      const response = await fetch(`/api/projects/${encodeURIComponent(trimmedName)}/agent/start-research`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          project_dir: selectedPath,
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }))
        throw new Error(errorData.detail || `HTTP ${response.status}`)
      }

      // Success - call the callback
      onStartAnalysis(trimmedName, selectedPath)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start analysis')
      setIsLoading(false)
    }
  }

  // Handle modal close
  const handleClose = () => {
    if (!isLoading) {
      onClose()
    }
  }

  if (!isOpen) return null

  // Folder selection step - uses larger modal
  if (step === 'folder') {
    return (
      <Dialog open={true} onOpenChange={(open) => !open && handleClose()}>
        <DialogContent className="sm:max-w-3xl max-h-[85vh] flex flex-col p-0">
          {/* Header */}
          <DialogHeader className="p-6 pb-4 border-b">
            <div className="flex items-center gap-3">
              <Search size={24} className="text-primary" />
              <div>
                <DialogTitle>Analyze Existing Codebase</DialogTitle>
                <DialogDescription>
                  Select a folder containing an existing codebase to analyze. The research agent will scan the code structure and document its findings.
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>

          {/* Folder Browser */}
          <div className="flex-1 overflow-hidden">
            <FolderBrowser
              onSelect={handleFolderSelect}
              onCancel={handleFolderCancel}
            />
          </div>
        </DialogContent>
      </Dialog>
    )
  }

  // Confirmation step - project name and start button
  return (
    <Dialog open={true} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <Search size={24} className="text-primary" />
            <div>
              <DialogTitle>Start Codebase Analysis</DialogTitle>
              <DialogDescription>
                Configure the analysis settings and start the research agent.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Selected folder display */}
          <div className="space-y-2">
            <Label className="text-muted-foreground">Selected Folder</Label>
            <div className="flex items-center gap-2 p-3 bg-muted rounded-md border">
              <Folder size={18} className="text-primary flex-shrink-0" />
              <span className="font-mono text-sm truncate">{selectedPath}</span>
            </div>
          </div>

          {/* Project name input */}
          <div className="space-y-2">
            <Label htmlFor="project-name">Project Name</Label>
            <Input
              id="project-name"
              type="text"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="my-project"
              pattern="^[a-zA-Z0-9_-]+$"
              maxLength={50}
              disabled={isLoading}
            />
            <p className="text-sm text-muted-foreground">
              Use letters, numbers, hyphens, and underscores only.
            </p>
          </div>

          {/* Error display */}
          {error && (
            <Alert variant="destructive">
              <AlertCircle size={16} />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Info about what happens next */}
          <div className="text-sm text-muted-foreground bg-muted/50 rounded-md p-3">
            <p className="font-medium mb-1">What happens next:</p>
            <ul className="list-disc list-inside space-y-1 text-xs">
              <li>The research agent will scan the codebase structure</li>
              <li>It documents file organization, patterns, and architecture</li>
              <li>Findings are saved for use in future development</li>
            </ul>
          </div>
        </div>

        {/* Loading state */}
        {isLoading && (
          <div className="flex items-center justify-center gap-2 text-muted-foreground py-2">
            <Loader2 size={16} className="animate-spin" />
            <span>Starting analysis...</span>
          </div>
        )}

        <DialogFooter className="sm:justify-between">
          <Button
            variant="ghost"
            onClick={handleBack}
            disabled={isLoading}
          >
            Back
          </Button>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              onClick={handleClose}
              disabled={isLoading}
            >
              Cancel
            </Button>
            <Button
              onClick={handleStartAnalysis}
              disabled={isLoading || !projectName.trim()}
            >
              {isLoading ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  Starting...
                </>
              ) : (
                <>
                  <Search size={16} />
                  Start Analysis
                </>
              )}
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
