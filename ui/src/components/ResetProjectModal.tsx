import { useState } from 'react'
import { Loader2, AlertTriangle, RotateCcw, Trash2, Check, X } from 'lucide-react'
import { useResetProject } from '../hooks/useProjects'
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

interface ResetProjectModalProps {
  isOpen: boolean
  projectName: string
  onClose: () => void
  onResetComplete?: (wasFullReset: boolean) => void
}

export function ResetProjectModal({
  isOpen,
  projectName,
  onClose,
  onResetComplete,
}: ResetProjectModalProps) {
  const [resetType, setResetType] = useState<'quick' | 'full'>('quick')
  const resetProject = useResetProject(projectName)

  const handleReset = async () => {
    const isFullReset = resetType === 'full'
    try {
      await resetProject.mutateAsync(isFullReset)
      onResetComplete?.(isFullReset)
      onClose()
    } catch {
      // Error is handled by the mutation state
    }
  }

  const handleClose = () => {
    if (!resetProject.isPending) {
      resetProject.reset()
      setResetType('quick')
      onClose()
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && handleClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <RotateCcw size={20} />
            Reset Project
          </DialogTitle>
          <DialogDescription>
            Reset <span className="font-semibold">{projectName}</span> to start fresh
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Reset Type Toggle */}
          <div className="flex rounded-lg border-2 border-border overflow-hidden">
            <button
              onClick={() => setResetType('quick')}
              disabled={resetProject.isPending}
              className={`flex-1 py-3 px-4 text-sm font-medium transition-colors flex items-center justify-center gap-2 ${
                resetType === 'quick'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-background text-foreground hover:bg-muted'
              } ${resetProject.isPending ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <RotateCcw size={16} />
              Quick Reset
            </button>
            <button
              onClick={() => setResetType('full')}
              disabled={resetProject.isPending}
              className={`flex-1 py-3 px-4 text-sm font-medium transition-colors flex items-center justify-center gap-2 ${
                resetType === 'full'
                  ? 'bg-destructive text-destructive-foreground'
                  : 'bg-background text-foreground hover:bg-muted'
              } ${resetProject.isPending ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <Trash2 size={16} />
              Full Reset
            </button>
          </div>

          {/* Warning Box */}
          <Alert variant={resetType === 'full' ? 'destructive' : 'default'} className="border-2">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              <div className="font-semibold mb-2">
                {resetType === 'quick' ? 'What will be deleted:' : 'What will be deleted:'}
              </div>
              <ul className="list-none space-y-1 text-sm">
                <li className="flex items-center gap-2">
                  <X size={14} className="text-destructive" />
                  All features and progress
                </li>
                <li className="flex items-center gap-2">
                  <X size={14} className="text-destructive" />
                  Assistant chat history
                </li>
                <li className="flex items-center gap-2">
                  <X size={14} className="text-destructive" />
                  Agent settings
                </li>
                {resetType === 'full' && (
                  <li className="flex items-center gap-2">
                    <X size={14} className="text-destructive" />
                    App spec and prompts
                  </li>
                )}
              </ul>
            </AlertDescription>
          </Alert>

          {/* What will be preserved */}
          <div className="bg-muted/50 rounded-lg border-2 border-border p-3">
            <div className="font-semibold mb-2 text-sm">
              {resetType === 'quick' ? 'What will be preserved:' : 'What will be preserved:'}
            </div>
            <ul className="list-none space-y-1 text-sm text-muted-foreground">
              {resetType === 'quick' ? (
                <>
                  <li className="flex items-center gap-2">
                    <Check size={14} className="text-green-600" />
                    App spec and prompts
                  </li>
                  <li className="flex items-center gap-2">
                    <Check size={14} className="text-green-600" />
                    Project code and files
                  </li>
                </>
              ) : (
                <>
                  <li className="flex items-center gap-2">
                    <Check size={14} className="text-green-600" />
                    Project code and files
                  </li>
                  <li className="flex items-center gap-2 text-muted-foreground/70">
                    <AlertTriangle size={14} />
                    Setup wizard will appear
                  </li>
                </>
              )}
            </ul>
          </div>

          {/* Error Message */}
          {resetProject.isError && (
            <Alert variant="destructive">
              <AlertDescription>
                {resetProject.error instanceof Error
                  ? resetProject.error.message
                  : 'Failed to reset project. Please try again.'}
              </AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter className="gap-2">
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={resetProject.isPending}
          >
            Cancel
          </Button>
          <Button
            variant={resetType === 'full' ? 'destructive' : 'default'}
            onClick={handleReset}
            disabled={resetProject.isPending}
          >
            {resetProject.isPending ? (
              <>
                <Loader2 className="animate-spin mr-2" size={16} />
                Resetting...
              </>
            ) : (
              <>
                {resetType === 'quick' ? 'Quick Reset' : 'Full Reset'}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
