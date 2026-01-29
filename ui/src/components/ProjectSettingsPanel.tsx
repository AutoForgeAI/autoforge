import { useState, useEffect } from 'react'
import { ChevronDown, ChevronRight, Settings, Loader2, Save, Trash2 } from 'lucide-react'
import { ModelConfigEditor, ModelConfigDisplay } from './ModelConfigEditor'
import {
  useProjectSettings,
  useUpdateProjectSettings,
  useDeleteProjectSettings,
  useAvailableModels,
  useMergedSettings,
} from '../hooks/useSettings'
import type { ModelConfig } from '../lib/types'

// Default built-in config (matches backend)
const BUILTIN_DEFAULTS: ModelConfig = {
  architect: 'claude-opus-4-5-20251101',
  initializer: 'claude-opus-4-5-20251101',
  coding: 'claude-sonnet-4-5-20250929',
  reviewer: 'claude-sonnet-4-5-20250929',
  testing: 'claude-3-5-haiku-20241022',
}

interface ProjectSettingsPanelProps {
  projectName: string
}

export function ProjectSettingsPanel({ projectName }: ProjectSettingsPanelProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const [useCustomSettings, setUseCustomSettings] = useState(false)
  const [localConfig, setLocalConfig] = useState<ModelConfig>(BUILTIN_DEFAULTS)
  const [hasChanges, setHasChanges] = useState(false)

  const { data: projectSettings, isLoading: settingsLoading } = useProjectSettings(projectName)
  const { data: mergedSettings, isLoading: mergedLoading } = useMergedSettings(projectName)
  const { data: availableModels = [], isLoading: modelsLoading } = useAvailableModels()
  const updateSettings = useUpdateProjectSettings(projectName)
  const deleteSettings = useDeleteProjectSettings(projectName)

  // Initialize state from server data
  useEffect(() => {
    if (projectSettings) {
      setUseCustomSettings(projectSettings.has_custom_settings)
      if (projectSettings.models) {
        setLocalConfig(projectSettings.models)
      }
      setHasChanges(false)
    }
  }, [projectSettings])

  // When toggling custom settings on, initialize from merged settings
  useEffect(() => {
    if (useCustomSettings && mergedSettings?.models && !projectSettings?.has_custom_settings) {
      setLocalConfig(mergedSettings.models)
    }
  }, [useCustomSettings, mergedSettings, projectSettings])

  const handleConfigChange = (config: ModelConfig) => {
    setLocalConfig(config)
    setHasChanges(true)
  }

  const handleToggleCustom = (checked: boolean) => {
    setUseCustomSettings(checked)
    if (checked && mergedSettings?.models) {
      // Initialize with current merged settings
      setLocalConfig(mergedSettings.models)
    }
    setHasChanges(true)
  }

  const handleSave = async () => {
    try {
      if (useCustomSettings) {
        await updateSettings.mutateAsync(localConfig)
      } else {
        await deleteSettings.mutateAsync()
      }
      setHasChanges(false)
    } catch (error) {
      console.error('Failed to save project settings:', error)
    }
  }

  const handleDiscard = () => {
    if (projectSettings) {
      setUseCustomSettings(projectSettings.has_custom_settings)
      if (projectSettings.models) {
        setLocalConfig(projectSettings.models)
      } else if (mergedSettings?.models) {
        setLocalConfig(mergedSettings.models)
      }
      setHasChanges(false)
    }
  }

  const isLoading = settingsLoading || mergedLoading || modelsLoading
  const isSaving = updateSettings.isPending || deleteSettings.isPending

  return (
    <div className="neo-card overflow-hidden">
      {/* Header - always visible */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-slate-800/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          {isExpanded ? (
            <ChevronDown size={18} className="text-slate-400" />
          ) : (
            <ChevronRight size={18} className="text-slate-400" />
          )}
          <div className="w-8 h-8 rounded-lg bg-indigo-500/20 flex items-center justify-center">
            <Settings size={16} className="text-indigo-400" />
          </div>
          <div className="text-left">
            <h3 className="text-sm font-medium text-white">Agent Configuration</h3>
            <p className="text-xs text-slate-400">
              {projectSettings?.has_custom_settings
                ? 'Using project-specific models'
                : 'Using app defaults'}
            </p>
          </div>
        </div>

        {/* Quick status indicator */}
        {!isExpanded && mergedSettings?.models && (
          <div className="hidden sm:block">
            <ModelConfigDisplay config={mergedSettings.models} />
          </div>
        )}
      </button>

      {/* Expanded content */}
      {isExpanded && (
        <div className="border-t border-slate-700/50 p-4 space-y-4">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 size={24} className="animate-spin text-indigo-400" />
            </div>
          ) : (
            <>
              {/* Custom settings toggle */}
              <label className="flex items-center gap-3 cursor-pointer">
                <input
                  type="checkbox"
                  checked={useCustomSettings}
                  onChange={(e) => handleToggleCustom(e.target.checked)}
                  className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-indigo-500 focus:ring-indigo-500 focus:ring-offset-0"
                />
                <div>
                  <span className="text-sm font-medium text-white">
                    Use custom model configuration for this project
                  </span>
                  <p className="text-xs text-slate-400">
                    Override app defaults with project-specific models
                  </p>
                </div>
              </label>

              {/* Model config editor */}
              <div className={useCustomSettings ? '' : 'opacity-50 pointer-events-none'}>
                <ModelConfigEditor
                  value={localConfig}
                  onChange={handleConfigChange}
                  availableModels={availableModels}
                  disabled={!useCustomSettings}
                  showPresets={true}
                />
              </div>

              {/* Source indicator */}
              {mergedSettings && (
                <div className="text-xs text-slate-500 bg-slate-800/50 p-3 rounded-lg">
                  <strong className="text-slate-400">Current source:</strong>{' '}
                  {mergedSettings.source}
                  {useCustomSettings && hasChanges && (
                    <span className="text-amber-400 ml-2">(unsaved changes)</span>
                  )}
                </div>
              )}

              {/* Actions */}
              {hasChanges && (
                <div className="flex items-center justify-end gap-3 pt-2 border-t border-slate-700/50">
                  <button
                    onClick={handleDiscard}
                    disabled={isSaving}
                    className="neo-btn neo-btn-ghost text-sm"
                  >
                    Discard
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={isSaving}
                    className="neo-btn neo-btn-primary text-sm"
                  >
                    {isSaving ? (
                      <Loader2 size={16} className="animate-spin" />
                    ) : useCustomSettings ? (
                      <Save size={16} />
                    ) : (
                      <Trash2 size={16} />
                    )}
                    {useCustomSettings ? 'Save Settings' : 'Reset to Defaults'}
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
