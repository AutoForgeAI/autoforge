/**
 * Auto-Improve Modal Component
 *
 * Configures per-project auto-improve mode: on an interval, the agent
 * creates one improvement feature, implements it, verifies, and commits.
 * Ticks are silently skipped while the agent is already running.
 */

import { useState, useEffect } from 'react'
import { Sparkles } from 'lucide-react'
import { useProject, useUpdateProjectSettings } from '../hooks/useProjects'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Alert, AlertDescription } from '@/components/ui/alert'

interface AutoImproveModalProps {
  projectName: string
  isOpen: boolean
  onClose: () => void
}

const PRESETS: { label: string; minutes: number }[] = [
  { label: '1 min', minutes: 1 },
  { label: '5 min', minutes: 5 },
  { label: '10 min', minutes: 10 },
  { label: '30 min', minutes: 30 },
  { label: '1 hour', minutes: 60 },
]

export function AutoImproveModal({ projectName, isOpen, onClose }: AutoImproveModalProps) {
  const { data: project } = useProject(projectName)
  const updateSettings = useUpdateProjectSettings(projectName)

  const [enabled, setEnabled] = useState(false)
  const [intervalMinutes, setIntervalMinutes] = useState(10)
  const [error, setError] = useState<string | null>(null)

  // Sync local form state with current project settings when the modal opens
  useEffect(() => {
    if (isOpen && project) {
      setEnabled(Boolean(project.auto_improve_enabled))
      setIntervalMinutes(project.auto_improve_interval_minutes || 10)
      setError(null)
    }
  }, [isOpen, project])

  const handleSave = async () => {
    setError(null)

    if (intervalMinutes < 1 || intervalMinutes > 1440) {
      setError('Interval must be between 1 and 1440 minutes')
      return
    }

    try {
      await updateSettings.mutateAsync({
        auto_improve_enabled: enabled,
        auto_improve_interval_minutes: intervalMinutes,
      })
      onClose()
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to save settings'
      setError(message)
    }
  }

  const handlePreset = (minutes: number) => {
    setIntervalMinutes(minutes)
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Sparkles size={18} className="text-primary" />
            Auto-Improve
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-6 py-2">
          {/* Explanatory copy */}
          <p className="text-sm text-muted-foreground">
            Auto-Improve runs the agent on a timer. Each tick it analyzes the
            codebase, picks one meaningful improvement, adds it to the Kanban,
            implements it, and commits with a short TLDR message. Ticks skip
            silently while the agent is already running.
          </p>

          {/* Enable toggle */}
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label htmlFor="auto-improve-enabled" className="font-medium">
                Enable auto-improve
              </Label>
              <p className="text-xs text-muted-foreground">
                When enabled, the agent will run every {intervalMinutes} minute
                {intervalMinutes === 1 ? '' : 's'}.
              </p>
            </div>
            <Switch
              id="auto-improve-enabled"
              checked={enabled}
              onCheckedChange={setEnabled}
            />
          </div>

          {/* Interval input */}
          <div className="space-y-2">
            <Label htmlFor="auto-improve-interval" className="font-medium">
              Interval (minutes)
            </Label>
            <Input
              id="auto-improve-interval"
              type="number"
              min={1}
              max={1440}
              value={intervalMinutes}
              onChange={(e) => setIntervalMinutes(Number(e.target.value))}
              disabled={!enabled}
              className="max-w-[140px]"
            />
            <div className="flex flex-wrap gap-1.5 pt-1">
              {PRESETS.map((preset) => (
                <Button
                  key={preset.minutes}
                  type="button"
                  size="sm"
                  variant={intervalMinutes === preset.minutes ? 'default' : 'outline'}
                  onClick={() => handlePreset(preset.minutes)}
                  disabled={!enabled}
                >
                  {preset.label}
                </Button>
              ))}
            </div>
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={updateSettings.isPending}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={updateSettings.isPending}>
            {updateSettings.isPending ? 'Saving...' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
