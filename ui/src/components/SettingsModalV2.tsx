/**
 * Settings Modal V2
 *
 * Unified settings interface with tabs for App vs Project settings.
 * Shows source indicators (project/app/default) for each setting.
 */

import { useState } from 'react'
import {
  Loader2,
  AlertCircle,
  Settings2,
  FolderCog,
  Cpu,
  Monitor,
  GitBranch,
  RotateCcw,
  Check,
  Activity,
  CheckCircle,
  AlertTriangle,
} from 'lucide-react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import * as api from '@/lib/api'
import type {
  AppSettingsV2Update,
  ProjectSettingsV2Update,
  ModelInfo,
} from '@/lib/types'
import { GitCheckpointPanel } from './GitCheckpointPanel'

interface SettingsModalV2Props {
  isOpen: boolean
  onClose: () => void
  projectName: string | null
}

type SettingSource = 'project' | 'app' | 'default'

function SourceBadge({ source }: { source: SettingSource }) {
  const config = {
    project: { label: 'Project', className: 'bg-blue-500/10 text-blue-600 border-blue-500/30' },
    app: { label: 'App', className: 'bg-green-500/10 text-green-600 border-green-500/30' },
    default: { label: 'Default', className: 'bg-gray-500/10 text-gray-600 border-gray-500/30' },
  }
  const c = config[source]
  return (
    <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ${c.className}`}>
      {c.label}
    </Badge>
  )
}

function ModelButtons({
  models,
  selectedId,
  onSelect,
  disabled,
}: {
  models: ModelInfo[]
  selectedId: string
  onSelect: (id: string) => void
  disabled: boolean
}) {
  return (
    <div className="grid grid-cols-2 gap-1.5">
      {models.map((model) => (
        <button
          key={model.id}
          onClick={() => onSelect(model.id)}
          disabled={disabled}
          className={`py-1.5 px-2 text-xs font-medium transition-colors rounded-md border ${
            selectedId === model.id
              ? 'bg-primary text-primary-foreground border-primary'
              : 'bg-background text-foreground border-border hover:bg-muted hover:border-primary/50'
          } ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
        >
          {model.name}
        </button>
      ))}
    </div>
  )
}

function SettingRow({
  label,
  description,
  source,
  children,
  onReset,
}: {
  label: string
  description?: string
  source?: SettingSource
  children: React.ReactNode
  onReset?: () => void
}) {
  return (
    <div className="flex items-start justify-between gap-4 py-3">
      <div className="space-y-0.5 flex-1">
        <div className="flex items-center gap-2">
          <Label className="font-medium">{label}</Label>
          {source && <SourceBadge source={source} />}
        </div>
        {description && (
          <p className="text-sm text-muted-foreground">{description}</p>
        )}
      </div>
      <div className="flex items-center gap-2">
        {children}
        {onReset && source === 'project' && (
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6"
            onClick={onReset}
            title="Reset to app default"
          >
            <RotateCcw size={12} />
          </Button>
        )}
      </div>
    </div>
  )
}

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string
  icon: React.ElementType
  children: React.ReactNode
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2 text-sm font-semibold text-muted-foreground uppercase tracking-wide">
        <Icon size={14} />
        {title}
      </div>
      <div className="divide-y divide-border">{children}</div>
    </div>
  )
}

export function SettingsModalV2({ isOpen, onClose, projectName }: SettingsModalV2Props) {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'app' | 'project' | 'usage' | 'git'>('app')

  // Fetch app settings
  const { data: appSettings, isLoading: appLoading, error: appError } = useQuery({
    queryKey: ['settings-v2-app'],
    queryFn: api.getAppSettingsV2,
    enabled: isOpen,
  })

  // Fetch project settings
  const { data: projectSettings, isLoading: projectLoading, error: projectError } = useQuery({
    queryKey: ['settings-v2-project', projectName],
    queryFn: () => api.getProjectSettingsV2(projectName!),
    enabled: isOpen && !!projectName,
  })

  // Fetch effective settings for source tracking
  const { data: effectiveSettings } = useQuery({
    queryKey: ['settings-v2-effective', projectName],
    queryFn: () => api.getEffectiveSettingsV2(projectName || undefined),
    enabled: isOpen,
  })

  // Fetch available models
  const { data: modelsData } = useQuery({
    queryKey: ['available-models'],
    queryFn: api.getAvailableModels,
    enabled: isOpen,
  })

  // Fetch scheduler status for usage tab
  const { data: schedulerStatus, isLoading: schedulerLoading } = useQuery({
    queryKey: ['scheduler-status', projectName],
    queryFn: async () => {
      const response = await fetch(`/api/scheduler/${encodeURIComponent(projectName!)}/status`)
      if (!response.ok) throw new Error('Failed to fetch scheduler status')
      return response.json()
    },
    enabled: isOpen && !!projectName,
    refetchInterval: 10000, // Refresh every 10 seconds while modal is open
  })

  // Mutations
  const updateApp = useMutation({
    mutationFn: api.updateAppSettingsV2,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings-v2-app'] })
      queryClient.invalidateQueries({ queryKey: ['settings-v2-effective'] })
      queryClient.invalidateQueries({ queryKey: ['settings'] }) // Also invalidate old settings
    },
  })

  const updateProject = useMutation({
    mutationFn: ({ settings }: { settings: ProjectSettingsV2Update }) =>
      api.updateProjectSettingsV2(projectName!, settings),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings-v2-project', projectName] })
      queryClient.invalidateQueries({ queryKey: ['settings-v2-effective'] })
    },
  })

  const clearProjectSetting = useMutation({
    mutationFn: (key: string) => api.clearProjectSettingV2(projectName!, key),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings-v2-project', projectName] })
      queryClient.invalidateQueries({ queryKey: ['settings-v2-effective'] })
    },
  })

  const resetAppSettings = useMutation({
    mutationFn: api.resetAppSettingsV2,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings-v2-app'] })
      queryClient.invalidateQueries({ queryKey: ['settings-v2-effective'] })
      queryClient.invalidateQueries({ queryKey: ['settings'] })
    },
  })

  const resetProjectSettings = useMutation({
    mutationFn: () => api.resetProjectSettingsV2(projectName!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings-v2-project', projectName] })
      queryClient.invalidateQueries({ queryKey: ['settings-v2-effective'] })
    },
  })

  const models = modelsData?.models ?? []
  const isSaving = updateApp.isPending || updateProject.isPending
  const isLoading = appLoading || (projectName && projectLoading)

  // Get source for a setting
  const getSource = (key: string): SettingSource => {
    return (effectiveSettings?.sources?.[key] as SettingSource) || 'default'
  }

  // Get effective value for a setting
  const getEffective = <T,>(key: string, fallback: T): T => {
    const value = effectiveSettings?.settings?.[key]
    return (value !== undefined ? value : fallback) as T
  }

  // Handle app setting changes
  const handleAppChange = (update: AppSettingsV2Update) => {
    if (!isSaving) {
      updateApp.mutate(update)
    }
  }

  // Handle project setting changes
  const handleProjectChange = (update: ProjectSettingsV2Update) => {
    if (!isSaving && projectName) {
      updateProject.mutate({ settings: update })
    }
  }

  // Reset project setting to app default
  const handleResetProjectSetting = (key: string) => {
    if (projectName) {
      clearProjectSetting.mutate(key)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-xl max-h-[85vh] flex flex-col">
        <DialogHeader className="shrink-0 pb-2">
          <DialogTitle className="flex items-center gap-2">
            <Settings2 size={20} />
            Settings
            {isSaving && <Loader2 className="animate-spin" size={16} />}
          </DialogTitle>
        </DialogHeader>

        <Tabs
          value={activeTab}
          onValueChange={(v) => setActiveTab(v as 'app' | 'project' | 'usage' | 'git')}
          className="flex-1 flex flex-col overflow-hidden"
        >
          <TabsList className="grid w-full grid-cols-4 shrink-0">
            <TabsTrigger value="app" className="gap-1.5 text-xs">
              <Settings2 size={14} />
              App
            </TabsTrigger>
            <TabsTrigger value="project" disabled={!projectName} className="gap-1.5 text-xs">
              <FolderCog size={14} />
              Project
            </TabsTrigger>
            <TabsTrigger value="usage" disabled={!projectName} className="gap-1.5 text-xs">
              <Activity size={14} />
              Usage
            </TabsTrigger>
            <TabsTrigger value="git" disabled={!projectName} className="gap-1.5 text-xs">
              <GitBranch size={14} />
              Git
            </TabsTrigger>
          </TabsList>

          {/* Loading State */}
          {isLoading && (
            <div className="flex items-center justify-center py-8 flex-1">
              <Loader2 className="animate-spin" size={24} />
              <span className="ml-2">Loading settings...</span>
            </div>
          )}

          {/* Error State */}
          {(appError || projectError) && (
            <Alert variant="destructive" className="mt-4">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                Failed to load settings. Please try again.
              </AlertDescription>
            </Alert>
          )}

          {/* App Settings Tab */}
          <TabsContent value="app" className="flex-1 overflow-y-auto mt-4 pr-2 -mr-2">
            {appSettings && (
              <div className="space-y-6">
                {/* Models Section */}
                <Section title="Models" icon={Cpu}>
                  <div className="space-y-4 py-3">
                    <div>
                      <Label className="text-xs text-muted-foreground mb-1.5 block">
                        Coding Agents
                      </Label>
                      <ModelButtons
                        models={models}
                        selectedId={appSettings.coderModel}
                        onSelect={(id) => handleAppChange({ coderModel: id })}
                        disabled={isSaving}
                      />
                    </div>
                    <div>
                      <Label className="text-xs text-muted-foreground mb-1.5 block">
                        Testing Agents
                      </Label>
                      <ModelButtons
                        models={models}
                        selectedId={appSettings.testerModel}
                        onSelect={(id) => handleAppChange({ testerModel: id })}
                        disabled={isSaving}
                      />
                    </div>
                    <div>
                      <Label className="text-xs text-muted-foreground mb-1.5 block">
                        Initializer Agent
                      </Label>
                      <ModelButtons
                        models={models}
                        selectedId={appSettings.initializerModel}
                        onSelect={(id) => handleAppChange({ initializerModel: id })}
                        disabled={isSaving}
                      />
                    </div>
                  </div>
                </Section>

                {/* Agents Section */}
                <Section title="Agents" icon={Cpu}>
                  <SettingRow
                    label="YOLO Mode"
                    description="Skip testing for rapid prototyping"
                  >
                    <Switch
                      checked={appSettings.yoloMode}
                      onCheckedChange={(v) => handleAppChange({ yoloMode: v })}
                      disabled={isSaving}
                    />
                  </SettingRow>
                  <SettingRow
                    label="Regression Agents"
                    description="Number of regression testing agents (0 = disabled)"
                  >
                    <div className="flex rounded-lg border overflow-hidden">
                      {[0, 1, 2, 3].map((n) => (
                        <button
                          key={n}
                          onClick={() => handleAppChange({ testingAgentRatio: n })}
                          disabled={isSaving}
                          className={`px-3 py-1 text-sm font-medium transition-colors ${
                            appSettings.testingAgentRatio === n
                              ? 'bg-primary text-primary-foreground'
                              : 'bg-background text-foreground hover:bg-muted'
                          }`}
                        >
                          {n}
                        </button>
                      ))}
                    </div>
                  </SettingRow>
                  <SettingRow
                    label="Auto Resume"
                    description="Automatically resume after crashes"
                  >
                    <Switch
                      checked={appSettings.autoResume}
                      onCheckedChange={(v) => handleAppChange({ autoResume: v })}
                      disabled={isSaving}
                    />
                  </SettingRow>
                  <SettingRow
                    label="Pause on Error"
                    description="Pause agent when feature fails repeatedly"
                  >
                    <Switch
                      checked={appSettings.pauseOnError}
                      onCheckedChange={(v) => handleAppChange({ pauseOnError: v })}
                      disabled={isSaving}
                    />
                  </SettingRow>
                </Section>

                {/* UI Section */}
                <Section title="Interface" icon={Monitor}>
                  <SettingRow
                    label="Show Debug Panel"
                    description="Expand debug panel by default"
                  >
                    <Switch
                      checked={appSettings.showDebugPanel}
                      onCheckedChange={(v) => handleAppChange({ showDebugPanel: v })}
                      disabled={isSaving}
                    />
                  </SettingRow>
                  <SettingRow
                    label="Celebrate Completion"
                    description="Show confetti when features complete"
                  >
                    <Switch
                      checked={appSettings.celebrateOnComplete}
                      onCheckedChange={(v) => handleAppChange({ celebrateOnComplete: v })}
                      disabled={isSaving}
                    />
                  </SettingRow>
                </Section>

                {/* Git Section */}
                <Section title="Git" icon={GitBranch}>
                  <SettingRow
                    label="Auto Commit"
                    description="Automatically commit after each feature"
                  >
                    <Switch
                      checked={appSettings.autoCommit}
                      onCheckedChange={(v) => handleAppChange({ autoCommit: v })}
                      disabled={isSaving}
                    />
                  </SettingRow>
                  <SettingRow
                    label="Auto Create PRs"
                    description="Create pull requests automatically"
                  >
                    <Switch
                      checked={appSettings.createPullRequests}
                      onCheckedChange={(v) => handleAppChange({ createPullRequests: v })}
                      disabled={isSaving}
                    />
                  </SettingRow>
                </Section>

                {/* Reset All Button */}
                <div className="pt-4 border-t border-border">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => resetAppSettings.mutate()}
                    disabled={resetAppSettings.isPending}
                    className="w-full gap-2 text-muted-foreground hover:text-foreground"
                  >
                    <RotateCcw size={14} />
                    {resetAppSettings.isPending ? 'Resetting...' : 'Reset All to Defaults'}
                  </Button>
                </div>
              </div>
            )}
          </TabsContent>

          {/* Project Settings Tab */}
          <TabsContent value="project" className="flex-1 overflow-y-auto mt-4 pr-2 -mr-2">
            {!projectName ? (
              <div className="flex items-center justify-center h-32 text-muted-foreground">
                Select a project to configure project-specific settings
              </div>
            ) : projectSettings && (
              <div className="space-y-6">
                <Alert>
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>
                    Project settings override app settings. Clear a setting to use the app default.
                  </AlertDescription>
                </Alert>

                {/* Models Section */}
                <Section title="Model Overrides" icon={Cpu}>
                  <div className="space-y-4 py-3">
                    <div>
                      <div className="flex items-center gap-2 mb-1.5">
                        <Label className="text-xs text-muted-foreground">Coding Agents</Label>
                        <SourceBadge source={getSource('coderModel')} />
                        {projectSettings.coderModel && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-5 w-5"
                            onClick={() => handleResetProjectSetting('coderModel')}
                          >
                            <RotateCcw size={10} />
                          </Button>
                        )}
                      </div>
                      <ModelButtons
                        models={models}
                        selectedId={getEffective('coderModel', appSettings?.coderModel || '')}
                        onSelect={(id) => handleProjectChange({ coderModel: id })}
                        disabled={isSaving}
                      />
                    </div>
                    <div>
                      <div className="flex items-center gap-2 mb-1.5">
                        <Label className="text-xs text-muted-foreground">Testing Agents</Label>
                        <SourceBadge source={getSource('testerModel')} />
                        {projectSettings.testerModel && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-5 w-5"
                            onClick={() => handleResetProjectSetting('testerModel')}
                          >
                            <RotateCcw size={10} />
                          </Button>
                        )}
                      </div>
                      <ModelButtons
                        models={models}
                        selectedId={getEffective('testerModel', appSettings?.testerModel || '')}
                        onSelect={(id) => handleProjectChange({ testerModel: id })}
                        disabled={isSaving}
                      />
                    </div>
                  </div>
                </Section>

                {/* Agents Section */}
                <Section title="Agent Overrides" icon={Cpu}>
                  <SettingRow
                    label="YOLO Mode"
                    description="Override app-level YOLO setting"
                    source={getSource('yoloMode')}
                    onReset={projectSettings.yoloMode !== null ? () => handleResetProjectSetting('yoloMode') : undefined}
                  >
                    <Switch
                      checked={getEffective('yoloMode', false)}
                      onCheckedChange={(v) => handleProjectChange({ yoloMode: v })}
                      disabled={isSaving}
                    />
                  </SettingRow>
                  <SettingRow
                    label="Regression Agents"
                    description="Override regression agent count"
                    source={getSource('testingAgentRatio')}
                    onReset={projectSettings.testingAgentRatio !== null ? () => handleResetProjectSetting('testingAgentRatio') : undefined}
                  >
                    <div className="flex rounded-lg border overflow-hidden">
                      {[0, 1, 2, 3].map((n) => (
                        <button
                          key={n}
                          onClick={() => handleProjectChange({ testingAgentRatio: n })}
                          disabled={isSaving}
                          className={`px-3 py-1 text-sm font-medium transition-colors ${
                            getEffective('testingAgentRatio', 1) === n
                              ? 'bg-primary text-primary-foreground'
                              : 'bg-background text-foreground hover:bg-muted'
                          }`}
                        >
                          {n}
                        </button>
                      ))}
                    </div>
                  </SettingRow>
                </Section>

                {/* Git Section */}
                <Section title="Git Overrides" icon={GitBranch}>
                  <SettingRow
                    label="Auto Commit"
                    description="Override auto-commit for this project"
                    source={getSource('autoCommit')}
                    onReset={projectSettings.autoCommit !== null ? () => handleResetProjectSetting('autoCommit') : undefined}
                  >
                    <Switch
                      checked={getEffective('autoCommit', false)}
                      onCheckedChange={(v) => handleProjectChange({ autoCommit: v })}
                      disabled={isSaving}
                    />
                  </SettingRow>
                </Section>

                {/* Reset All Button */}
                <div className="pt-4 border-t border-border">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => resetProjectSettings.mutate()}
                    disabled={resetProjectSettings.isPending}
                    className="w-full gap-2 text-muted-foreground hover:text-foreground"
                  >
                    <RotateCcw size={14} />
                    {resetProjectSettings.isPending ? 'Resetting...' : 'Clear All Project Overrides'}
                  </Button>
                </div>
              </div>
            )}
          </TabsContent>

          {/* Usage Tab */}
          <TabsContent value="usage" className="flex-1 overflow-y-auto mt-4 pr-2 -mr-2">
            {!projectName ? (
              <div className="flex items-center justify-center h-32 text-muted-foreground">
                Select a project to view usage metrics
              </div>
            ) : schedulerLoading ? (
              <div className="flex items-center justify-center h-32">
                <Loader2 className="animate-spin" size={24} />
                <span className="ml-2">Loading usage data...</span>
              </div>
            ) : schedulerStatus ? (
              <div className="space-y-6">
                {/* Usage Level Summary */}
                <div className={`p-4 rounded-lg border ${
                  schedulerStatus.level === 'healthy' ? 'bg-green-500/10 border-green-500/30' :
                  schedulerStatus.level === 'moderate' ? 'bg-yellow-500/10 border-yellow-500/30' :
                  schedulerStatus.level === 'low' ? 'bg-orange-500/10 border-orange-500/30' :
                  'bg-red-500/10 border-red-500/30'
                }`}>
                  <div className="flex items-center gap-3">
                    {schedulerStatus.level === 'healthy' ? (
                      <CheckCircle className="text-green-500" size={24} />
                    ) : schedulerStatus.level === 'moderate' ? (
                      <Activity className="text-yellow-500" size={24} />
                    ) : schedulerStatus.level === 'low' ? (
                      <AlertTriangle className="text-orange-500" size={24} />
                    ) : (
                      <AlertCircle className="text-red-500" size={24} />
                    )}
                    <div>
                      <h3 className="font-semibold capitalize">{schedulerStatus.level} Usage</h3>
                      <p className="text-sm text-muted-foreground">{schedulerStatus.statusMessage}</p>
                    </div>
                  </div>
                </div>

                {/* Session Metrics */}
                <Section title="Session Metrics" icon={Activity}>
                  <div className="py-3 space-y-4">
                    {/* Messages Progress */}
                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span>Messages</span>
                        <span className="font-mono">
                          {schedulerStatus.session.messagesSent} / {schedulerStatus.session.messagesLimit}
                        </span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className={`h-full transition-all ${
                            schedulerStatus.session.messagePercentUsed > 80 ? 'bg-red-500' :
                            schedulerStatus.session.messagePercentUsed > 50 ? 'bg-yellow-500' :
                            'bg-green-500'
                          }`}
                          style={{ width: `${Math.min(100, schedulerStatus.session.messagePercentUsed)}%` }}
                        />
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">
                        {schedulerStatus.session.messagesRemaining} messages remaining ({Math.round(schedulerStatus.session.messagePercentUsed)}% used)
                      </p>
                    </div>

                    {/* Context Progress */}
                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span>Context Window</span>
                        <span className="font-mono">
                          {Math.round(schedulerStatus.session.contextPercentUsed)}%
                        </span>
                      </div>
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div
                          className={`h-full transition-all ${
                            schedulerStatus.session.contextPercentUsed > 80 ? 'bg-red-500' :
                            schedulerStatus.session.contextPercentUsed > 50 ? 'bg-yellow-500' :
                            'bg-green-500'
                          }`}
                          style={{ width: `${Math.min(100, schedulerStatus.session.contextPercentUsed)}%` }}
                        />
                      </div>
                      <p className="text-xs text-muted-foreground mt-1">
                        {schedulerStatus.session.contextRemaining?.toLocaleString() ?? 0} tokens remaining
                      </p>
                    </div>
                  </div>
                </Section>

                {/* Scheduling Info */}
                <Section title="Scheduling" icon={Cpu}>
                  <SettingRow label="Current Strategy" description="Based on usage level">
                    <Badge variant="outline" className="capitalize">
                      {schedulerStatus.strategy.replace('_', ' ')}
                    </Badge>
                  </SettingRow>
                  <SettingRow label="Recommended Concurrency" description="Suggested agent count">
                    <span className="font-mono">{schedulerStatus.recommendedConcurrency}</span>
                  </SettingRow>
                  <SettingRow label="Features Completed" description="This session">
                    <span className="font-mono">
                      {schedulerStatus.session.featuresCompleted} / {schedulerStatus.session.featuresAttempted}
                    </span>
                  </SettingRow>
                </Section>

                {/* Token Details */}
                <Section title="Token Usage" icon={Monitor}>
                  <div className="py-3 grid grid-cols-2 gap-4">
                    <div className="p-3 bg-muted/50 rounded-lg">
                      <p className="text-xs text-muted-foreground">Input Tokens</p>
                      <p className="font-mono text-lg">{schedulerStatus.session.inputTokensUsed?.toLocaleString() ?? 0}</p>
                    </div>
                    <div className="p-3 bg-muted/50 rounded-lg">
                      <p className="text-xs text-muted-foreground">Output Tokens</p>
                      <p className="font-mono text-lg">{schedulerStatus.session.outputTokensUsed?.toLocaleString() ?? 0}</p>
                    </div>
                  </div>
                </Section>
              </div>
            ) : (
              <div className="flex items-center justify-center h-32 text-muted-foreground">
                No usage data available
              </div>
            )}
          </TabsContent>

          {/* Git Tab */}
          <TabsContent value="git" className="flex-1 overflow-y-auto mt-4 pr-2 -mr-2">
            {!projectName ? (
              <div className="flex items-center justify-center h-32 text-muted-foreground">
                Select a project to manage git checkpoints
              </div>
            ) : (
              <div className="space-y-4">
                <div className="text-sm text-muted-foreground">
                  Create checkpoint commits with detailed messages. All changes will be staged and committed.
                </div>
                <GitCheckpointPanel projectName={projectName} />
              </div>
            )}
          </TabsContent>
        </Tabs>

        {/* Save indicator */}
        {(updateApp.isSuccess || updateProject.isSuccess) && (
          <div className="flex items-center gap-2 text-green-600 text-sm mt-2">
            <Check size={14} />
            Settings saved
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

export default SettingsModalV2
