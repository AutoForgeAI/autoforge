import { useState } from 'react'
import { Loader2, AlertTriangle, RefreshCw, ArrowRight, X } from 'lucide-react'
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

interface ReinitializeFeaturesModalProps {
  isOpen: boolean
  projectName: string
  existingFeatureCount: number
  passingCount: number
  onReinitialize: () => Promise<void>
  onKeepFeatures: () => void
  onCancel: () => void
}

export function ReinitializeFeaturesModal({
  isOpen,
  projectName,
  existingFeatureCount,
  passingCount,
  onReinitialize,
  onKeepFeatures,
  onCancel,
}: ReinitializeFeaturesModalProps) {
  const [isReinitializing, setIsReinitializing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const allComplete = passingCount === existingFeatureCount && existingFeatureCount > 0
  const percentComplete = existingFeatureCount > 0
    ? Math.round((passingCount / existingFeatureCount) * 100)
    : 0

  const handleReinitialize = async () => {
    setIsReinitializing(true)
    setError(null)
    try {
      await onReinitialize()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to reinitialize features')
      setIsReinitializing(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && !isReinitializing && onCancel()}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <RefreshCw size={20} />
            New Spec Created
          </DialogTitle>
          <DialogDescription>
            Your new app spec has been saved for <span className="font-semibold">{projectName}</span>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Warning about existing features */}
          <Alert variant={allComplete ? 'destructive' : 'default'} className="border-2">
            <AlertTriangle className="h-4 w-4" />
            <AlertDescription>
              <div className="font-semibold mb-2">
                This project has existing features
              </div>
              <div className="text-sm space-y-1">
                <p>
                  <span className="font-medium">{existingFeatureCount}</span> features in database
                  {passingCount > 0 && (
                    <span className="ml-1">
                      ({passingCount} complete - {percentComplete}%)
                    </span>
                  )}
                </p>
                {allComplete && (
                  <p className="text-destructive font-medium mt-2">
                    All features are complete! Reinitializing will discard this progress.
                  </p>
                )}
              </div>
            </AlertDescription>
          </Alert>

          {/* Explanation */}
          <div className="bg-muted/50 rounded-lg border-2 border-border p-4 text-sm">
            <p className="mb-3">
              To use your new spec, you need to <span className="font-medium">reinitialize</span> the
              feature database. This will:
            </p>
            <ul className="list-disc list-inside space-y-1 text-muted-foreground">
              <li>Clear all existing features from the database</li>
              <li>Start the initializer agent to create features from the new spec</li>
              <li>Your project code files will be preserved</li>
            </ul>
          </div>

          {/* Error message */}
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter className="flex-col sm:flex-row gap-2">
          <Button
            variant="outline"
            onClick={onCancel}
            disabled={isReinitializing}
            className="sm:order-1"
          >
            <X size={16} className="mr-2" />
            Cancel
          </Button>
          <Button
            variant="secondary"
            onClick={onKeepFeatures}
            disabled={isReinitializing}
            className="sm:order-2"
          >
            <ArrowRight size={16} className="mr-2" />
            Keep Old Features
          </Button>
          <Button
            variant={allComplete ? 'destructive' : 'default'}
            onClick={handleReinitialize}
            disabled={isReinitializing}
            className="sm:order-3"
          >
            {isReinitializing ? (
              <>
                <Loader2 className="animate-spin mr-2" size={16} />
                Reinitializing...
              </>
            ) : (
              <>
                <RefreshCw size={16} className="mr-2" />
                Reinitialize Features
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
