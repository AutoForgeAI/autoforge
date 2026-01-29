import { Cpu, Zap, Sparkles, Scale, Rocket } from 'lucide-react'
import type { ModelConfig, AvailableModel } from '../lib/types'

// Agent type configuration for display
const AGENT_TYPES = [
  {
    key: 'architect' as keyof ModelConfig,
    label: 'Architect',
    description: 'System design and architecture decisions',
    icon: Sparkles,
  },
  {
    key: 'initializer' as keyof ModelConfig,
    label: 'Initializer',
    description: 'Spec analysis and feature creation',
    icon: Rocket,
  },
  {
    key: 'coding' as keyof ModelConfig,
    label: 'Coding',
    description: 'Code implementation',
    icon: Cpu,
  },
  {
    key: 'reviewer' as keyof ModelConfig,
    label: 'Reviewer',
    description: 'Code review and quality checks',
    icon: Scale,
  },
  {
    key: 'testing' as keyof ModelConfig,
    label: 'Testing',
    description: 'Test execution and validation',
    icon: Zap,
  },
]

// Preset configurations
const PRESETS = {
  costOptimized: {
    label: 'Cost Optimized',
    description: 'Minimize cost while maintaining quality',
    config: {
      architect: 'claude-opus-4-5-20251101',
      initializer: 'claude-opus-4-5-20251101',
      coding: 'claude-sonnet-4-5-20250929',
      reviewer: 'claude-sonnet-4-5-20250929',
      testing: 'claude-3-5-haiku-20241022',
    },
  },
  qualityFirst: {
    label: 'Quality First',
    description: 'Use Opus for all tasks',
    config: {
      architect: 'claude-opus-4-5-20251101',
      initializer: 'claude-opus-4-5-20251101',
      coding: 'claude-opus-4-5-20251101',
      reviewer: 'claude-opus-4-5-20251101',
      testing: 'claude-opus-4-5-20251101',
    },
  },
  allSonnet: {
    label: 'Balanced',
    description: 'Use Sonnet for all tasks',
    config: {
      architect: 'claude-sonnet-4-5-20250929',
      initializer: 'claude-sonnet-4-5-20250929',
      coding: 'claude-sonnet-4-5-20250929',
      reviewer: 'claude-sonnet-4-5-20250929',
      testing: 'claude-sonnet-4-5-20250929',
    },
  },
  speedFirst: {
    label: 'Speed First',
    description: 'Use Haiku for fast iterations',
    config: {
      architect: 'claude-sonnet-4-5-20250929',
      initializer: 'claude-sonnet-4-5-20250929',
      coding: 'claude-3-5-haiku-20241022',
      reviewer: 'claude-3-5-haiku-20241022',
      testing: 'claude-3-5-haiku-20241022',
    },
  },
}

interface ModelConfigEditorProps {
  value: ModelConfig
  onChange: (config: ModelConfig) => void
  availableModels: AvailableModel[]
  disabled?: boolean
  showPresets?: boolean
}

export function ModelConfigEditor({
  value,
  onChange,
  availableModels,
  disabled = false,
  showPresets = true,
}: ModelConfigEditorProps) {
  const handleModelChange = (agentKey: keyof ModelConfig, modelId: string) => {
    onChange({
      ...value,
      [agentKey]: modelId,
    })
  }

  const applyPreset = (presetKey: keyof typeof PRESETS) => {
    onChange(PRESETS[presetKey].config)
  }

  return (
    <div className="space-y-4">
      {/* Presets */}
      {showPresets && (
        <div className="space-y-2">
          <label className="text-sm font-medium text-slate-300">Presets</label>
          <div className="flex flex-wrap gap-2">
            {Object.entries(PRESETS).map(([key, preset]) => (
              <button
                key={key}
                onClick={() => applyPreset(key as keyof typeof PRESETS)}
                disabled={disabled}
                className="neo-btn neo-btn-ghost text-xs py-1.5 px-3"
                title={preset.description}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Agent type rows */}
      <div className="space-y-3">
        {AGENT_TYPES.map(({ key, label, description, icon: Icon }) => (
          <div
            key={key}
            className="flex items-center gap-4 p-3 rounded-lg bg-slate-800/50 border border-slate-700/50"
          >
            {/* Icon and label */}
            <div className="flex items-center gap-3 min-w-[140px]">
              <div className="w-8 h-8 rounded-lg bg-slate-700/50 flex items-center justify-center">
                <Icon size={16} className="text-indigo-400" />
              </div>
              <div>
                <div className="text-sm font-medium text-white">{label}</div>
                <div className="text-xs text-slate-400 hidden sm:block">{description}</div>
              </div>
            </div>

            {/* Model selector */}
            <div className="flex-1">
              <select
                value={value[key]}
                onChange={(e) => handleModelChange(key, e.target.value)}
                disabled={disabled}
                className="neo-input w-full text-sm"
              >
                {availableModels.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.name}
                  </option>
                ))}
              </select>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// Compact version for displaying current config (read-only)
interface ModelConfigDisplayProps {
  config: ModelConfig
  source?: string
}

export function ModelConfigDisplay({
  config,
  source,
}: ModelConfigDisplayProps) {
  const getModelShortName = (modelId: string) => {
    if (modelId.includes('opus')) return 'Opus'
    if (modelId.includes('sonnet')) return 'Sonnet'
    if (modelId.includes('haiku')) return 'Haiku'
    return modelId.split('-')[1] || modelId
  }

  return (
    <div className="space-y-2">
      {source && (
        <div className="text-xs text-slate-500 mb-2">
          Source: {source}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {AGENT_TYPES.map(({ key, label }) => (
          <div
            key={key}
            className="flex items-center gap-1.5 px-2 py-1 rounded bg-slate-800/50 text-xs"
          >
            <span className="text-slate-400">{label}:</span>
            <span className="text-indigo-300 font-medium">
              {getModelShortName(config[key])}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
