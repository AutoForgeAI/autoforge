import { useState, useCallback, useEffect } from 'react'
import { ProjectBreadcrumb } from './Breadcrumb'
import type { PhaseData } from './PhaseCard'
import type { Feature } from '../lib/types'

// Navigation levels
export type NavigationLevel = 'projects' | 'project' | 'phase' | 'feature' | 'task'

export interface NavigationState {
  level: NavigationLevel
  projectName?: string
  phaseId?: number
  phaseName?: string
  featureId?: number
  featureName?: string
  taskId?: number
  taskName?: string
}

interface DrillDownContainerProps {
  children: (props: {
    level: NavigationLevel
    state: NavigationState
    navigateTo: (state: Partial<NavigationState>) => void
    navigateUp: () => void
    navigateToProject: (projectName: string) => void
    navigateToPhase: (phase: PhaseData) => void
    navigateToFeature: (feature: { id: number; name: string }) => void
    navigateToTask: (task: Feature) => void
  }) => React.ReactNode
  initialState?: Partial<NavigationState>
  onNavigate?: (state: NavigationState) => void
}

function getNavigationLevel(state: NavigationState): NavigationLevel {
  if (state.taskId) return 'task'
  if (state.featureId) return 'feature'
  if (state.phaseId) return 'phase'
  if (state.projectName) return 'project'
  return 'projects'
}

export function DrillDownContainer({
  children,
  initialState,
  onNavigate,
}: DrillDownContainerProps) {
  const [state, setState] = useState<NavigationState>(() => ({
    level: 'projects',
    ...initialState,
  }))

  // Update level when state changes
  useEffect(() => {
    const newLevel = getNavigationLevel(state)
    if (newLevel !== state.level) {
      setState(prev => ({ ...prev, level: newLevel }))
    }
  }, [state.projectName, state.phaseId, state.featureId, state.taskId])

  // Notify parent of navigation changes
  useEffect(() => {
    onNavigate?.(state)
  }, [state, onNavigate])

  // Update URL hash for bookmarkable navigation
  useEffect(() => {
    const hash = buildHashFromState(state)
    if (window.location.hash !== hash) {
      window.history.pushState(null, '', hash || '#')
    }
  }, [state])

  // Listen for browser back/forward
  useEffect(() => {
    const handlePopState = () => {
      const newState = parseHashToState(window.location.hash)
      setState(prev => ({ ...prev, ...newState }))
    }
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  // Initialize from URL hash on mount
  useEffect(() => {
    const hashState = parseHashToState(window.location.hash)
    if (Object.keys(hashState).length > 0) {
      setState(prev => ({ ...prev, ...hashState }))
    }
  }, [])

  const navigateTo = useCallback((partial: Partial<NavigationState>) => {
    setState(prev => {
      const newState = { ...prev, ...partial }
      newState.level = getNavigationLevel(newState)
      return newState
    })
  }, [])

  const navigateUp = useCallback(() => {
    setState(prev => {
      if (prev.taskId) {
        return { ...prev, taskId: undefined, taskName: undefined, level: 'feature' }
      }
      if (prev.featureId) {
        return { ...prev, featureId: undefined, featureName: undefined, level: 'phase' }
      }
      if (prev.phaseId) {
        return { ...prev, phaseId: undefined, phaseName: undefined, level: 'project' }
      }
      if (prev.projectName) {
        return { level: 'projects' }
      }
      return prev
    })
  }, [])

  const navigateToProject = useCallback((projectName: string) => {
    setState({
      level: 'project',
      projectName,
    })
  }, [])

  const navigateToPhase = useCallback((phase: PhaseData) => {
    setState(prev => ({
      ...prev,
      level: 'phase',
      phaseId: phase.id,
      phaseName: phase.name,
      featureId: undefined,
      featureName: undefined,
      taskId: undefined,
      taskName: undefined,
    }))
  }, [])

  const navigateToFeature = useCallback((feature: { id: number; name: string }) => {
    setState(prev => ({
      ...prev,
      level: 'feature',
      featureId: feature.id,
      featureName: feature.name,
      taskId: undefined,
      taskName: undefined,
    }))
  }, [])

  const navigateToTask = useCallback((task: Feature) => {
    setState(prev => ({
      ...prev,
      level: 'task',
      taskId: task.id,
      taskName: task.name,
    }))
  }, [])

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Escape or Backspace to go up (when not in input)
      if ((e.key === 'Escape' || e.key === 'Backspace') &&
          !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) {
        e.preventDefault()
        navigateUp()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [navigateUp])

  return (
    <div className="flex flex-col h-full">
      {/* Breadcrumb Navigation */}
      <div className="flex-shrink-0 p-4 border-b border-[var(--color-neo-border)] bg-[var(--color-neo-card)]">
        <ProjectBreadcrumb
          projectName={state.projectName}
          phaseName={state.phaseName}
          featureName={state.featureName}
          taskName={state.taskName}
          onNavigateHome={() => setState({ level: 'projects' })}
          onNavigateProject={() => setState(prev => ({
            level: 'project',
            projectName: prev.projectName,
          }))}
          onNavigatePhase={() => setState(prev => ({
            level: 'phase',
            projectName: prev.projectName,
            phaseId: prev.phaseId,
            phaseName: prev.phaseName,
          }))}
          onNavigateFeature={() => setState(prev => ({
            level: 'feature',
            projectName: prev.projectName,
            phaseId: prev.phaseId,
            phaseName: prev.phaseName,
            featureId: prev.featureId,
            featureName: prev.featureName,
          }))}
        />
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-auto">
        {children({
          level: state.level,
          state,
          navigateTo,
          navigateUp,
          navigateToProject,
          navigateToPhase,
          navigateToFeature,
          navigateToTask,
        })}
      </div>
    </div>
  )
}

// URL hash utilities
function buildHashFromState(state: NavigationState): string {
  const parts: string[] = []
  if (state.projectName) {
    parts.push(`project=${encodeURIComponent(state.projectName)}`)
  }
  if (state.phaseId) {
    parts.push(`phase=${state.phaseId}`)
  }
  if (state.featureId) {
    parts.push(`feature=${state.featureId}`)
  }
  if (state.taskId) {
    parts.push(`task=${state.taskId}`)
  }
  return parts.length > 0 ? `#${parts.join('&')}` : ''
}

function parseHashToState(hash: string): Partial<NavigationState> {
  if (!hash || hash === '#') return {}

  const params = new URLSearchParams(hash.slice(1))
  const state: Partial<NavigationState> = {}

  const project = params.get('project')
  if (project) state.projectName = decodeURIComponent(project)

  const phase = params.get('phase')
  if (phase) state.phaseId = parseInt(phase, 10)

  const feature = params.get('feature')
  if (feature) state.featureId = parseInt(feature, 10)

  const task = params.get('task')
  if (task) state.taskId = parseInt(task, 10)

  return state
}
