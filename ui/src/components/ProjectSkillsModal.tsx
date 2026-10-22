/**
 * Project Skills Modal Component
 *
 * Choose which Claude Code skills are installed in the project's
 * .claude/skills/ directory. Installing "project-learnings" enables
 * skill learning: coding agents update it after each passing feature.
 */

import { useEffect, useMemo, useState } from 'react'
import { Loader2, Wand2 } from 'lucide-react'
import {
  useInstallProjectSkills,
  useProjectSkills,
  useRemoveProjectSkill,
  useSkillLibrary,
} from '../hooks/useProjects'
import type { SkillInfo } from '../lib/types'
import { SkillPicker } from './SkillPicker'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'

const LEARNINGS_SKILL = 'project-learnings'

interface ProjectSkillsModalProps {
  projectName: string
  isOpen: boolean
  onClose: () => void
}

export function ProjectSkillsModal({ projectName, isOpen, onClose }: ProjectSkillsModalProps) {
  const library = useSkillLibrary(isOpen)
  const installedQuery = useProjectSkills(projectName, isOpen)
  const installSkills = useInstallProjectSkills(projectName)
  const removeSkill = useRemoveProjectSkill(projectName)

  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [error, setError] = useState<string | null>(null)

  const installed = useMemo(
    () => new Set((installedQuery.data ?? []).map((s) => s.name)),
    [installedQuery.data]
  )

  // Library skills, plus any skills that only exist in the project
  const skills = useMemo<SkillInfo[]>(() => {
    const libraryNames = new Set((library.data ?? []).map((s) => s.name))
    const projectOnly = (installedQuery.data ?? []).filter((s) => !libraryNames.has(s.name))
    return [...(library.data ?? []), ...projectOnly]
  }, [library.data, installedQuery.data])

  // Sync selection with what's installed whenever the dialog opens
  useEffect(() => {
    if (isOpen && installedQuery.data) {
      setSelected(new Set(installedQuery.data.map((s) => s.name)))
      setError(null)
    }
  }, [isOpen, installedQuery.data])

  const toAdd = [...selected].filter((name) => !installed.has(name))
  const toRemove = [...installed].filter(
    (name) => !selected.has(name) && !skills.find((s) => s.name === name)?.required
  )
  const isSaving = installSkills.isPending || removeSkill.isPending
  const isLoading = library.isLoading || installedQuery.isLoading

  const handleToggle = (name: string, checked: boolean) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (checked) next.add(name)
      else next.delete(name)
      return next
    })
  }

  const handleSave = async () => {
    setError(null)
    try {
      if (toAdd.length > 0) {
        await installSkills.mutateAsync(toAdd)
      }
      for (const name of toRemove) {
        await removeSkill.mutateAsync(name)
      }
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update skills')
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[560px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Wand2 size={18} className="text-primary" />
            Project Skills
          </DialogTitle>
          <DialogDescription>
            Skills are copied into this project&apos;s <code className="font-mono">.claude/skills/</code> and
            loaded by the coding agents. Enable <span className="font-mono">{LEARNINGS_SKILL}</span> to have
            agents record what they learn after each passing feature.
          </DialogDescription>
        </DialogHeader>

        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 size={20} className="animate-spin text-muted-foreground" />
          </div>
        ) : (
          <SkillPicker skills={skills} selected={selected} onToggle={handleToggle} disabled={isSaving} />
        )}

        {toRemove.includes(LEARNINGS_SKILL) && (
          <Alert>
            <AlertDescription>
              Removing <span className="font-mono">{LEARNINGS_SKILL}</span> deletes everything the agents have
              recorded in it.
            </AlertDescription>
          </Alert>
        )}

        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={isSaving}>
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={isSaving || isLoading || (toAdd.length === 0 && toRemove.length === 0)}
          >
            {isSaving && <Loader2 size={16} className="animate-spin" />}
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
