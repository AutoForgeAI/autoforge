/**
 * Import Project Modal Component
 *
 * Registers an existing AutoForge project folder (one that already has
 * .autoforge/features.db or a spec) so it can be re-opened, e.g. after a
 * reinstall or when moving to a new machine:
 * 1. Select the existing project folder
 * 2. Confirm the project name and import
 */

import { useState } from 'react'
import { ArrowLeft, FolderInput, Loader2 } from 'lucide-react'
import { useImportProject } from '../hooks/useProjects'
import { FolderBrowser } from './FolderBrowser'
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

type Step = 'folder' | 'name'

interface ImportProjectModalProps {
  isOpen: boolean
  onClose: () => void
  onProjectImported: (projectName: string) => void
}

function nameFromPath(path: string): string {
  const base = path.replace(/[\\/]+$/, '').split(/[\\/]/).pop() || ''
  return base.replace(/[^a-zA-Z0-9_-]/g, '-').slice(0, 50)
}

function parentOf(path: string): string | undefined {
  const parent = path.replace(/[\\/]+$/, '').replace(/[\\/][^\\/]*$/, '')
  return /[\\/]/.test(parent) ? parent : undefined
}

export function ImportProjectModal({
  isOpen,
  onClose,
  onProjectImported,
}: ImportProjectModalProps) {
  const [step, setStep] = useState<Step>('folder')
  const [projectPath, setProjectPath] = useState<string | null>(null)
  const [projectName, setProjectName] = useState('')
  const [error, setError] = useState<string | null>(null)

  const importProject = useImportProject()

  if (!isOpen) return null

  const handleClose = () => {
    setStep('folder')
    setProjectPath(null)
    setProjectName('')
    setError(null)
    onClose()
  }

  const handleFolderSelect = (path: string) => {
    setProjectPath(path)
    setProjectName(nameFromPath(path))
    setError(null)
    setStep('name')
  }

  const handleBack = () => {
    setError(null)
    setStep('folder')
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = projectName.trim()

    if (!trimmed) {
      setError('Please enter a project name')
      return
    }

    if (!/^[a-zA-Z0-9_-]+$/.test(trimmed)) {
      setError('Project name can only contain letters, numbers, hyphens, and underscores')
      return
    }

    if (!projectPath) {
      setStep('folder')
      return
    }

    setError(null)
    try {
      const project = await importProject.mutateAsync({ name: trimmed, path: projectPath })
      onProjectImported(project.name)
      handleClose()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to import project')
    }
  }

  if (step === 'folder') {
    return (
      <Dialog open={true} onOpenChange={(open) => !open && handleClose()}>
        <DialogContent className="sm:max-w-3xl max-h-[85vh] flex flex-col p-0">
          <DialogHeader className="p-6 pb-4 border-b">
            <div className="flex items-center gap-3">
              <FolderInput size={24} className="text-primary" />
              <div>
                <DialogTitle>Import Existing Project</DialogTitle>
                <DialogDescription>
                  Select the folder of a project previously created with AutoForge (it contains a <span className="font-mono">.autoforge</span> directory).
                </DialogDescription>
              </div>
            </div>
          </DialogHeader>

          <div className="flex-1 overflow-hidden">
            <FolderBrowser
              onSelect={handleFolderSelect}
              onCancel={handleClose}
              initialPath={projectPath ? parentOf(projectPath) : undefined}
            />
          </div>
        </DialogContent>
      </Dialog>
    )
  }

  return (
    <Dialog open={true} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Import Existing Project</DialogTitle>
          <DialogDescription>
            Features, progress, and prompts in this folder are kept as-is.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label>Folder</Label>
            <p className="text-sm font-mono break-all bg-muted rounded-md px-3 py-2">{projectPath}</p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="import-project-name">Project Name</Label>
            <Input
              id="import-project-name"
              type="text"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              placeholder="my-awesome-app"
              pattern="^[a-zA-Z0-9_\-]+$"
              autoFocus
            />
            <p className="text-sm text-muted-foreground">
              Use letters, numbers, hyphens, and underscores only.
            </p>
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <DialogFooter className="sm:justify-between">
            <Button type="button" variant="ghost" onClick={handleBack} disabled={importProject.isPending}>
              <ArrowLeft size={16} />
              Back
            </Button>
            <Button type="submit" disabled={!projectName.trim() || importProject.isPending}>
              {importProject.isPending ? <Loader2 size={16} className="animate-spin" /> : <FolderInput size={16} />}
              Import Project
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
