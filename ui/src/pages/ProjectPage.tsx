import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQueryClient, useQuery } from '@tanstack/react-query'
import { useFeatures, useAgentStatus, useProjects } from '../hooks/useProjects'
import { useProjectWebSocket } from '../hooks/useWebSocket'
import { useFeatureSound } from '../hooks/useFeatureSound'
import { OlympusHeader } from '../components/OlympusHeader'
import { KanbanBoard } from '../components/KanbanBoard'
import { AgentControl } from '../components/AgentControl'
import { ProgressDashboard } from '../components/ProgressDashboard'
import { AddFeatureForm } from '../components/AddFeatureForm'
import { FeatureModal } from '../components/FeatureModal'
import { DebugLogViewer, type TabType } from '../components/DebugLogViewer'
import { AgentMissionControl } from '../components/AgentMissionControl'
import { AssistantFAB } from '../components/AssistantFAB'
import { AssistantPanel } from '../components/AssistantPanel'
import { ExpandProjectModal } from '../components/ExpandProjectModal'
import { SpecCreationChat } from '../components/SpecCreationChat'
import { SettingsModal } from '../components/SettingsModal'
// DevServerControl removed from header
import { ViewToggle, type ViewMode } from '../components/ViewToggle'
import { DependencyGraph } from '../components/DependencyGraph'
import { KeyboardShortcutsHelp } from '../components/KeyboardShortcutsHelp'
import { ResetProjectModal } from '../components/ResetProjectModal'
import { ProjectSetupRequired } from '../components/ProjectSetupRequired'
import { SpecEditorModal } from '../components/SpecEditorModal'
import { getDependencyGraph, startAgent, listSpecFiles, getModernizeStatus } from '../lib/api'
import { Loader2, RotateCcw } from 'lucide-react'
import type { Feature } from '../lib/types'

const VIEW_MODE_KEY = 'olympus-view-mode'
const COLLAPSED_DEBUG_PANEL_CLEARANCE = 48

type InitializerStatus = 'idle' | 'starting' | 'error'

export function ProjectPage() {
  const { name } = useParams<{ name: string }>()
  const navigate = useNavigate()
  const projectName = name ? decodeURIComponent(name) : null

  const [showAddFeature, setShowAddFeature] = useState(false)
  const [showExpandProject, setShowExpandProject] = useState(false)
  const [selectedFeature, setSelectedFeature] = useState<Feature | null>(null)
  const [debugOpen, setDebugOpen] = useState(false)
  const [debugPanelHeight, setDebugPanelHeight] = useState(288)
  const [debugActiveTab, setDebugActiveTab] = useState<TabType>('agent')
  const [assistantOpen, setAssistantOpen] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [showKeyboardHelp, setShowKeyboardHelp] = useState(false)
  const [showResetModal, setShowResetModal] = useState(false)
  const [showSpecChat, setShowSpecChat] = useState(false)
  const [specInitializerStatus, setSpecInitializerStatus] = useState<InitializerStatus>('idle')
  const [specInitializerError, setSpecInitializerError] = useState<string | null>(null)
  const [selectedSpecFile, setSelectedSpecFile] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<ViewMode>(() => {
    try {
      const stored = localStorage.getItem(VIEW_MODE_KEY)
      return (stored === 'graph' ? 'graph' : 'kanban') as ViewMode
    } catch {
      return 'kanban'
    }
  })

  const queryClient = useQueryClient()
  const { data: projects } = useProjects()
  const { data: features } = useFeatures(projectName)
  useAgentStatus(projectName)
  const wsState = useProjectWebSocket(projectName)

  const selectedProjectData = projects?.find(p => p.name === projectName)
  const hasSpec = selectedProjectData?.has_spec ?? true
  const isBrownfield = !!selectedProjectData?.target_stack

  // For brownfield projects, check spec files
  const { data: specList } = useQuery({
    queryKey: ['spec-files', projectName],
    queryFn: () => listSpecFiles(projectName!),
    enabled: !!projectName && isBrownfield,
    refetchInterval: (query) => {
      const analysisStatus = query.state.data?.analysis_status
      return analysisStatus === 'running' ? 5000 : 30000
    },
  })

  // Poll modernize status for brownfield projects
  const { data: modernizeStatus } = useQuery({
    queryKey: ['modernize-status', projectName],
    queryFn: () => getModernizeStatus(projectName!),
    enabled: !!projectName && isBrownfield,
    staleTime: 0,
    refetchOnMount: 'always',
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'complete' || status === 'error' ? false : 3000
    },
  })

  // Redirect to home if project doesn't exist
  useEffect(() => {
    if (projects && projectName && !projects.some(p => p.name === projectName)) {
      navigate('/', { replace: true })
    }
  }, [projects, projectName, navigate])

  const { data: graphData } = useQuery({
    queryKey: ['dependencyGraph', projectName],
    queryFn: () => getDependencyGraph(projectName!),
    enabled: !!projectName && viewMode === 'graph',
    refetchInterval: 5000,
  })

  useEffect(() => {
    try { localStorage.setItem(VIEW_MODE_KEY, viewMode) } catch { /* */ }
  }, [viewMode])

  useFeatureSound(features)


  const handleGraphNodeClick = useCallback((nodeId: number) => {
    const allFeatures = [
      ...(features?.pending ?? []),
      ...(features?.in_progress ?? []),
      ...(features?.done ?? []),
      ...(features?.needs_human_input ?? [])
    ]
    const feature = allFeatures.find(f => f.id === nodeId)
    if (feature) setSelectedFeature(feature)
  }, [features])

  /** Start coding agents after spec review is complete */
  const handleBeginCoding = async () => {
    if (!projectName) return
    try {
      await startAgent(projectName, { yoloMode: true, maxConcurrency: 3 })
      queryClient.invalidateQueries({ queryKey: ['agentStatus', projectName] })
      queryClient.invalidateQueries({ queryKey: ['features', projectName] })
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    } catch (err) {
      console.error('Failed to start agent:', err)
    }
  }

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return

      if (e.key === 'd' || e.key === 'D') { e.preventDefault(); setDebugOpen(prev => !prev) }
      if (e.key === 't' || e.key === 'T') {
        e.preventDefault()
        if (!debugOpen) { setDebugOpen(true); setDebugActiveTab('terminal') }
        else if (debugActiveTab === 'terminal') { setDebugOpen(false) }
        else { setDebugActiveTab('terminal') }
      }
      if ((e.key === 'n' || e.key === 'N') && projectName) { e.preventDefault(); setShowAddFeature(true) }
      if ((e.key === 'e' || e.key === 'E') && projectName && hasSpec && features &&
          (features.pending.length + features.in_progress.length + features.done.length + (features.needs_human_input?.length || 0)) > 0) {
        e.preventDefault(); setShowExpandProject(true)
      }
      if ((e.key === 'a' || e.key === 'A') && projectName) { e.preventDefault(); setAssistantOpen(prev => !prev) }
      if (e.key === ',') { e.preventDefault(); setShowSettings(true) }
      if ((e.key === 'g' || e.key === 'G') && projectName) { e.preventDefault(); setViewMode(prev => prev === 'kanban' ? 'graph' : 'kanban') }
      if (e.key === '?') { e.preventDefault(); setShowKeyboardHelp(true) }
      if ((e.key === 'r' || e.key === 'R') && projectName && !['running', 'pausing', 'paused_graceful'].includes(wsState.agentStatus)) {
        e.preventDefault(); setShowResetModal(true)
      }
      if (e.key === 'Escape') {
        if (showKeyboardHelp) setShowKeyboardHelp(false)
        else if (showResetModal) setShowResetModal(false)
        else if (showExpandProject) setShowExpandProject(false)
        else if (showSettings) setShowSettings(false)
        else if (assistantOpen) setAssistantOpen(false)
        else if (showAddFeature) setShowAddFeature(false)
        else if (selectedFeature) setSelectedFeature(null)
        else if (selectedSpecFile) setSelectedSpecFile(null)
        else if (debugOpen) setDebugOpen(false)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [projectName, showAddFeature, showExpandProject, selectedFeature, selectedSpecFile, debugOpen, debugActiveTab, assistantOpen, features, showSettings, showKeyboardHelp, viewMode, showResetModal, wsState.agentStatus, hasSpec])

  const progress = wsState.progress.total > 0 ? wsState.progress : {
    passing: features?.done.length ?? 0,
    total: (features?.pending.length ?? 0) + (features?.in_progress.length ?? 0) + (features?.done.length ?? 0) + (features?.needs_human_input?.length ?? 0),
    percentage: 0,
  }
  if (progress.total > 0 && progress.percentage === 0) {
    progress.percentage = Math.round((progress.passing / progress.total) * 100 * 10) / 10
  }

  if (!projectName) return null

  // Header right content: agent controls + settings
  const headerBtnStyle: React.CSSProperties = {
    width: '34px', height: '34px', borderRadius: '6px',
    border: '1px solid #DDEC90', background: 'transparent',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    cursor: 'pointer', color: '#7A8A00', transition: 'background 0.12s',
  }

  const headerRight = (
    <div className="flex items-center gap-2">
      <AgentControl
        projectName={projectName}
        status={wsState.agentStatus}
        defaultConcurrency={selectedProjectData?.default_concurrency}
      />
      <button
        onClick={() => setShowResetModal(true)}
        aria-label="Reset Odyssey"
        title="Reset (R)"
        disabled={['running', 'pausing', 'paused_graceful'].includes(wsState.agentStatus)}
        style={{
          ...headerBtnStyle,
          opacity: ['running', 'pausing', 'paused_graceful'].includes(wsState.agentStatus) ? 0.4 : 1,
          cursor: ['running', 'pausing', 'paused_graceful'].includes(wsState.agentStatus) ? 'not-allowed' : 'pointer',
        }}
        onMouseEnter={e => { if (!['running', 'pausing', 'paused_graceful'].includes(wsState.agentStatus)) (e.currentTarget as HTMLElement).style.background = '#F5F8D0' }}
        onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
      >
        <RotateCcw size={18} />
      </button>
    </div>
  )

  return (
    <div className="min-h-screen" style={{ background: '#FAFAF2' }}>
      <OlympusHeader projectName={projectName} rightContent={headerRight} />

      <main
        className="max-w-7xl mx-auto px-4 py-8"
        style={{ paddingBottom: debugOpen ? debugPanelHeight + 32 : COLLAPSED_DEBUG_PANEL_CLEARANCE }}
      >
        {/* Greenfield project without spec: show setup required */}
        {!hasSpec && !isBrownfield ? (
          <ProjectSetupRequired
            projectName={projectName}
            projectPath={selectedProjectData?.path}
            onCreateWithClaude={() => setShowSpecChat(true)}
            onEditManually={() => setDebugOpen(true)}
          />
        ) : (
          <div className="space-y-8">
            <ProgressDashboard
              passing={progress.passing}
              total={progress.total}
              percentage={progress.percentage}
              isConnected={wsState.isConnected}
              logs={wsState.activeAgents.length === 0 ? wsState.logs : undefined}
              agentStatus={wsState.activeAgents.length === 0 ? wsState.agentStatus : undefined}
            />

            <AgentMissionControl
              agents={wsState.activeAgents}
              orchestratorStatus={wsState.orchestratorStatus}
              recentActivity={wsState.recentActivity}
              getAgentLogs={wsState.getAgentLogs}
            />

            {/* Initializing state */}
            {features &&
             features.pending.length === 0 &&
             features.in_progress.length === 0 &&
             features.done.length === 0 &&
             (features.needs_human_input?.length || 0) === 0 &&
             wsState.agentStatus === 'running' && (
              <div style={{
                padding: '32px', textAlign: 'center',
                background: '#FFFFFF', border: '1px solid #DDEC90', borderRadius: '8px',
              }}>
                <Loader2 size={32} className="animate-spin" style={{ color: '#BBCB64', margin: '0 auto 16px' }} />
                <h3 style={{ fontSize: '20px', fontWeight: 700, color: '#1A1A00', marginBottom: '8px' }}>
                  Analyzing and generating features...
                </h3>
                <p style={{ fontSize: '14px', color: '#6A6A20' }}>
                  The agents are studying your specification and preparing the quest. This may take a moment.
                </p>
              </div>
            )}

            {/* View Toggle */}
            {features && (features.pending.length + features.in_progress.length + features.done.length + (features.needs_human_input?.length || 0)) > 0 && (
              <div className="flex justify-center">
                <ViewToggle viewMode={viewMode} onViewModeChange={setViewMode} />
              </div>
            )}

            {/* Kanban or Graph */}
            {viewMode === 'kanban' ? (
              <KanbanBoard
                features={features}
                onFeatureClick={setSelectedFeature}
                onAddFeature={() => setShowAddFeature(true)}
                onExpandProject={() => setShowExpandProject(true)}
                activeAgents={wsState.activeAgents}
                onCreateSpec={() => setShowSpecChat(true)}
                hasSpec={hasSpec}
                specList={isBrownfield ? specList ?? null : null}
                isBrownfield={isBrownfield}
                isAnalyzingSpecs={modernizeStatus?.status === 'running'}
                onSpecFileClick={(filename) => setSelectedSpecFile(filename)}
                onSpecApproved={() => {
                  queryClient.invalidateQueries({ queryKey: ['spec-files', projectName] })
                }}
                onBeginCoding={handleBeginCoding}
              />
            ) : (
              <div style={{
                height: '600px', borderRadius: '8px', overflow: 'hidden',
                border: '1px solid #DDEC90', background: '#FAFAF2',
              }}>
                {graphData ? (
                  <DependencyGraph
                    graphData={graphData}
                    onNodeClick={handleGraphNodeClick}
                    activeAgents={wsState.activeAgents}
                  />
                ) : (
                  <div className="h-full flex items-center justify-center">
                    <Loader2 size={32} className="animate-spin" style={{ color: '#BBCB64' }} />
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Modals */}
      {showAddFeature && (
        <AddFeatureForm projectName={projectName} onClose={() => setShowAddFeature(false)} />
      )}

      {selectedFeature && (
        <FeatureModal feature={selectedFeature} projectName={projectName} onClose={() => setSelectedFeature(null)} />
      )}

      {showExpandProject && hasSpec && (
        <ExpandProjectModal
          isOpen={showExpandProject}
          projectName={projectName}
          onClose={() => setShowExpandProject(false)}
          onFeaturesAdded={() => queryClient.invalidateQueries({ queryKey: ['features', projectName] })}
        />
      )}

      {showSpecChat && (
        <div className="fixed inset-0 z-50 bg-background">
          <SpecCreationChat
            projectName={projectName}
            onComplete={async (_specPath, yoloMode) => {
              setSpecInitializerStatus('starting')
              try {
                await startAgent(projectName, { yoloMode: yoloMode ?? false, maxConcurrency: 3 })
                setShowSpecChat(false)
                setSpecInitializerStatus('idle')
                queryClient.invalidateQueries({ queryKey: ['projects'] })
                queryClient.invalidateQueries({ queryKey: ['features', projectName] })
              } catch (err) {
                setSpecInitializerStatus('error')
                setSpecInitializerError(err instanceof Error ? err.message : 'Failed to start agent')
              }
            }}
            onCancel={() => { setShowSpecChat(false); setSpecInitializerStatus('idle') }}
            onExitToProject={() => { setShowSpecChat(false); setSpecInitializerStatus('idle') }}
            initializerStatus={specInitializerStatus}
            initializerError={specInitializerError}
            onRetryInitializer={() => { setSpecInitializerError(null); setSpecInitializerStatus('idle') }}
          />
        </div>
      )}

      {/* Spec Editor Modal */}
      {selectedSpecFile && (
        <SpecEditorModal
          projectName={projectName}
          filename={selectedSpecFile}
          isOpen={!!selectedSpecFile}
          onClose={() => setSelectedSpecFile(null)}
          onApproved={() => {
            setSelectedSpecFile(null)
            queryClient.invalidateQueries({ queryKey: ['spec-files', projectName] })
          }}
        />
      )}

      {/* Debug Panel */}
      <DebugLogViewer
        logs={wsState.logs}
        devLogs={wsState.devLogs}
        isOpen={debugOpen}
        onToggle={() => setDebugOpen(!debugOpen)}
        onClear={wsState.clearLogs}
        onClearDevLogs={wsState.clearDevLogs}
        onHeightChange={setDebugPanelHeight}
        projectName={projectName}
        activeTab={debugActiveTab}
        onTabChange={setDebugActiveTab}
      />

      {/* Assistant */}
      {!showExpandProject && !showSpecChat && (
        <>
          <AssistantFAB onClick={() => setAssistantOpen(!assistantOpen)} isOpen={assistantOpen} />
          <AssistantPanel projectName={projectName} isOpen={assistantOpen} onClose={() => setAssistantOpen(false)} />
        </>
      )}

      <SettingsModal isOpen={showSettings} onClose={() => setShowSettings(false)} />
      <KeyboardShortcutsHelp isOpen={showKeyboardHelp} onClose={() => setShowKeyboardHelp(false)} />

      {showResetModal && (
        <ResetProjectModal
          isOpen={showResetModal}
          projectName={projectName}
          onClose={() => setShowResetModal(false)}
          onResetComplete={(wasFullReset) => { if (wasFullReset) setShowSpecChat(true) }}
        />
      )}

    </div>
  )
}
