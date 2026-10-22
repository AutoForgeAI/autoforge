/**
 * Skill Picker Component
 *
 * Checkbox list of Claude Code skills. Used when creating a project and in
 * the project Skills dialog to choose which skills the agents can use.
 */

import { Brain } from 'lucide-react'
import type { SkillInfo, SkillSource } from '../lib/types'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'

const SOURCE_LABELS: Record<SkillSource, string> = {
  bundled: 'AutoForge',
  user: '~/.autoforge/skills',
  claude: '~/.claude/skills',
  project: 'Project',
}

interface SkillPickerProps {
  skills: SkillInfo[]
  selected: Set<string>
  onToggle: (name: string, checked: boolean) => void
  disabled?: boolean
}

export function SkillPicker({ skills, selected, onToggle, disabled = false }: SkillPickerProps) {
  if (skills.length === 0) {
    return (
      <p className="text-sm text-muted-foreground py-4 text-center">
        No skills found. Add skills to <code className="font-mono">~/.autoforge/skills/</code>.
      </p>
    )
  }

  return (
    <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
      {skills.map((skill) => {
        const id = `skill-${skill.name}`
        const checked = skill.required || selected.has(skill.name)
        return (
          <label
            key={skill.name}
            htmlFor={id}
            className={`flex items-start gap-3 rounded-lg border p-3 transition-colors ${
              skill.required || disabled ? 'opacity-80' : 'cursor-pointer hover:border-primary'
            }`}
          >
            <Checkbox
              id={id}
              checked={checked}
              disabled={skill.required || disabled}
              onCheckedChange={(value) => onToggle(skill.name, value === true)}
              className="mt-0.5"
            />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                {skill.recommended && <Brain size={14} className="text-primary" />}
                <span className="font-mono text-sm font-semibold">{skill.name}</span>
                {skill.recommended && <Badge>Self-improving</Badge>}
                {skill.required && <Badge variant="secondary">Always included</Badge>}
                <Badge variant="outline" className="text-xs">{SOURCE_LABELS[skill.source]}</Badge>
              </div>
              {skill.description && (
                <p className="text-xs text-muted-foreground mt-1 line-clamp-3">{skill.description}</p>
              )}
            </div>
          </label>
        )
      })}
    </div>
  )
}
