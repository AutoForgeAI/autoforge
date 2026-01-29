import { useState, useEffect } from 'react'
import { X, Settings, Loader2, RotateCcw, Save } from 'lucide-react'
import { ModelConfigEditor } from './ModelConfigEditor'
import { useAppSettings, useUpdateAppSettings, useAvailableModels } from '../hooks/useSettings'
import type { ModelConfig } from '../lib/types'

// Default built-in config (matches backend)
const BUILTIN_DEFAULTS: ModelConfig = {
  architect: 'claude-opus-4-5-20251101',
  initializer: 'claude-opus-4-5-20251101',
  coding: 'claude-sonnet-4-5-20250929',
  reviewer: 'claude-sonnet-4-5-20250929',
  testing: 'claude-3-5-haiku-20241022',
}

interface SettingsModalProps {
  isOpen: boolean
  onClose: () => void
}

export function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const { data: appSettings, isLoading: settingsLoading } = useAppSettings()
  const { data: availableModels = [], isLoading: modelsLoading } = useAvailableModels()
  const updateSettings = useUpdateAppSettings()

  // Local state for editing
  const [localConfig, setLocalConfig] = useState<ModelConfig>(BUILTIN_DEFAULTS)
  const [hasChanges, setHasChanges] = useState(false)

  // Initialize local state from server data
  useEffect(() => {
    if (appSettings?.models) {
      setLocalConfig(appSettings.models)
      setHasChanges(false)
    }
  }, [appSettings])

  // Track changes
  const handleConfigChange = (config: ModelConfig) => {
    setLocalConfig(config)
    // Check if different from saved
    if (appSettings?.models) {
      const isDifferent = Object.keys(config).some(
        key => config[key as keyof ModelConfig] !== appSettings.models[key as keyof ModelConfig]
      )
      setHasChanges(isDifferent)
    } else {
      setHasChanges(true)
    }
  }

  const handleSave = async () => {
    try {
      await updateSettings.mutateAsync(localConfig)
      setHasChanges(false)
    } catch (error) {
      console.error('Failed to save settings:', error)
    }
  }

  const handleReset = () => {
    setLocalConfig(BUILTIN_DEFAULTS)
    setHasChanges(true)
  }

  const handleClose = () => {
    // Reset to saved state on close
    if (appSettings?.models) {
      setLocalConfig(appSettings.models)
    }
    setHasChanges(false)
    onClose()
  }

  if (!isOpen) return null

  const isLoading = settingsLoading || modelsLoading

  return (
    <div className="neo-modal-backdrop" onClick={handleClose}>
      <div
        className="neo-modal w-full max-w-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-700/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/20 flex items-center justify-center">
              <Settings size={20} className="text-indigo-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Settings</h2>
              <p className="text-sm text-slate-400">Configure default models for each agent type</p>
            </div>
          </div>
          <button
            onClick={handleClose}
            className="neo-btn neo-btn-ghost p-2"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 size={32} className="animate-spin text-indigo-400" />
            </div>
          ) : (
            <div className="space-y-6">
              {/* Section header */}
              <div>
                <h3 className="text-sm font-medium text-slate-300 mb-1">
                  Default Model Configuration
                </h3>
                <p className="text-xs text-slate-500">
                  These settings apply to all new projects. You can override them per-project.
                </p>
              </div>

              {/* Model config editor */}
              <ModelConfigEditor
                value={localConfig}
                onChange={handleConfigChange}
                availableModels={availableModels}
                showPresets={true}
              />

              {/* Info text */}
              <div className="text-xs text-slate-500 bg-slate-800/50 p-3 rounded-lg">
                <strong className="text-slate-400">Tip:</strong> Use Opus for complex reasoning tasks
                (architect, initializer), Sonnet for balanced quality/speed (coding, review), and
                Haiku for fast, lightweight tasks (testing).
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-6 border-t border-slate-700/50">
          <button
            onClick={handleReset}
            disabled={isLoading}
            className="neo-btn neo-btn-ghost text-sm"
          >
            <RotateCcw size={16} />
            Reset to Defaults
          </button>

          <div className="flex gap-3">
            <button
              onClick={handleClose}
              className="neo-btn neo-btn-ghost text-sm"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isLoading || updateSettings.isPending || !hasChanges}
              className="neo-btn neo-btn-primary text-sm"
            >
              {updateSettings.isPending ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Save size={16} />
              )}
              Save Changes
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
