/**
 * AppContext - Central state provider for the AutoForge UI.
 *
 * Extracts all application state from the monolithic App.tsx into a shared
 * React context so that deeply nested components can access state without
 * prop-drilling. Provides the `useAppContext()` hook for consumption.
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
  type ReactNode,
} from 'react'
import { useQueryClient, useQuery, type QueryClient } from '@tanstack/react-query'
import { useProjects, useFeatures, useAgentStatus, useSettings } from '../hooks/useProjects'
import { useProjectWebSocket } from '../hooks/useWebSocket'
import { useFeatureSound } from '../hooks/useFeatureSound'
import { useCelebration } from '../hooks/useCelebration'
import { useTheme, type ThemeId, type ThemeOption } from '../hooks/useTheme'
import { getDependencyGraph } from '../lib/api'
import type {
  Feature,
  FeatureListResponse,
  ProjectSummary,
  Settings,
  DependencyGraph,
} from '../lib/types'
import { TooltipProvider } from '@/components/ui/tooltip'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ViewId = 'dashboard' | 'kanban' | 'graph' | 'browsers' | 'terminal' | 'logs' | 'assistant' | 'settings'

type InitializerStatus = 'idle' | 'starting' | 'error'

/** Progress summary derived from WebSocket state and feature data. */
interface Progress {
  passing: number
  total: number
  percentage: number
}

/**
 * The full return type of `useProjectWebSocket`. We reference it structurally
 * rather than importing a non-exported interface to keep the coupling minimal.
 */
type WebSocketState = ReturnType<typeof useProjectWebSocket>

/** Shape of the value exposed by AppContext. */
interface AppContextValue {
  // -- Project selection --
  selectedProject: string | null
  setSelectedProject: (project: string | null) => void

  // -- View navigation --
  activeView: ViewId
  setActiveView: (view: ViewId) => void

  // -- Sidebar --
  sidebarCollapsed: boolean
  setSidebarCollapsed: (collapsed: boolean) => void
  toggleSidebar: () => void

  // -- Modals --
  showAddFeature: boolean
  setShowAddFeature: (open: boolean) => void
  showExpandProject: boolean
  setShowExpandProject: (open: boolean) => void
  selectedFeature: Feature | null
  setSelectedFeature: (feature: Feature | null) => void
  showSettings: boolean
  setShowSettings: (open: boolean) => void
  showKeyboardHelp: boolean
  setShowKeyboardHelp: (open: boolean) => void
  showResetModal: boolean
  setShowResetModal: (open: boolean) => void
  showSpecChat: boolean
  setShowSpecChat: (open: boolean) => void
  isSpecCreating: boolean
  setIsSpecCreating: (creating: boolean) => void
  assistantOpen: boolean
  setAssistantOpen: (open: boolean) => void

  // -- Setup --
  setupComplete: boolean
  setSetupComplete: (complete: boolean) => void

  // -- Spec initializer --
  specInitializerStatus: InitializerStatus
  setSpecInitializerStatus: (status: InitializerStatus) => void
  specInitializerError: string | null
  setSpecInitializerError: (error: string | null) => void

  // -- Queries / data --
  projects: ProjectSummary[] | undefined
  projectsLoading: boolean
  features: FeatureListResponse | undefined
  settings: Settings | undefined
  wsState: WebSocketState
  theme: ThemeId
  setTheme: (theme: ThemeId) => void
  darkMode: boolean
  toggleDarkMode: () => void
  themes: ThemeOption[]
  currentTheme: ThemeOption
  queryClient: QueryClient

  // -- Derived state --
  selectedProjectData: ProjectSummary | undefined
  hasSpec: boolean
  progress: Progress

  // -- Graph --
  graphData: DependencyGraph | undefined
  handleGraphNodeClick: (nodeId: number) => void
}

// ---------------------------------------------------------------------------
// LocalStorage helpers
// ---------------------------------------------------------------------------

const STORAGE_KEYS = {
  selectedProject: 'autoforge-selected-project',
  activeView: 'autoforge-active-view',
  sidebarCollapsed: 'autoforge-sidebar-collapsed',
} as const

function readStorage<T extends string>(key: string, fallback: T): T {
  try {
    const stored = localStorage.getItem(key)
    return (stored ?? fallback) as T
  } catch {
    return fallback
  }
}

function writeStorage(key: string, value: string | null): void {
  try {
    if (value === null) {
      localStorage.removeItem(key)
    } else {
      localStorage.setItem(key, value)
    }
  } catch {
    // localStorage not available
  }
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const AppContext = createContext<AppContextValue | null>(null)

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function AppProvider({ children }: { children: ReactNode }) {
  // ---- Project ----
  const [selectedProject, setSelectedProjectRaw] = useState<string | null>(() =>
    readStorage(STORAGE_KEYS.selectedProject, '') || null,
  )

  const setSelectedProject = useCallback((project: string | null) => {
    setSelectedProjectRaw(project)
    writeStorage(STORAGE_KEYS.selectedProject, project)
  }, [])

  // ---- View navigation ----
  const [activeView, setActiveViewRaw] = useState<ViewId>(() => {
    const stored = readStorage(STORAGE_KEYS.activeView, 'dashboard')
    const valid: ViewId[] = ['dashboard', 'kanban', 'graph', 'browsers', 'terminal', 'logs', 'assistant', 'settings']
    return valid.includes(stored as ViewId) ? (stored as ViewId) : 'dashboard'
  })

  const setActiveView = useCallback((view: ViewId) => {
    setActiveViewRaw(view)
    writeStorage(STORAGE_KEYS.activeView, view)
  }, [])

  // ---- Sidebar ----
  const [sidebarCollapsed, setSidebarCollapsedRaw] = useState<boolean>(() => {
    try {
      return localStorage.getItem(STORAGE_KEYS.sidebarCollapsed) === 'true'
    } catch {
      return false
    }
  })

  const setSidebarCollapsed = useCallback((collapsed: boolean) => {
    setSidebarCollapsedRaw(collapsed)
    writeStorage(STORAGE_KEYS.sidebarCollapsed, String(collapsed))
  }, [])

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsedRaw(prev => {
      const next = !prev
      writeStorage(STORAGE_KEYS.sidebarCollapsed, String(next))
      return next
    })
  }, [])

  // ---- Modals ----
  const [showAddFeature, setShowAddFeature] = useState(false)
  const [showExpandProject, setShowExpandProject] = useState(false)
  const [selectedFeature, setSelectedFeature] = useState<Feature | null>(null)
  const [showSettings, setShowSettings] = useState(false)
  const [showKeyboardHelp, setShowKeyboardHelp] = useState(false)
  const [showResetModal, setShowResetModal] = useState(false)
  const [showSpecChat, setShowSpecChat] = useState(false)
  const [isSpecCreating, setIsSpecCreating] = useState(false)
  const [assistantOpen, setAssistantOpen] = useState(false)

  // ---- Setup ----
  const [setupComplete, setSetupComplete] = useState(true) // optimistic default

  // ---- Spec initializer ----
  const [specInitializerStatus, setSpecInitializerStatus] = useState<InitializerStatus>('idle')
  const [specInitializerError, setSpecInitializerError] = useState<string | null>(null)

  // ---- Queries ----
  const queryClient = useQueryClient()
  const { data: projects, isLoading: projectsLoading } = useProjects()
  const { data: features } = useFeatures(selectedProject)
  const { data: settings } = useSettings()
  useAgentStatus(selectedProject) // keep polling for status updates
  const wsState = useProjectWebSocket(selectedProject)
  const { theme, setTheme, darkMode, toggleDarkMode, themes, currentTheme } = useTheme()

  // ---- Derived state ----
  const selectedProjectData = projects?.find(p => p.name === selectedProject)
  const hasSpec = selectedProjectData?.has_spec ?? true

  const progress = useMemo<Progress>(() => {
    // Prefer WebSocket progress when available; fall back to feature counts
    if (wsState.progress.total > 0) {
      return {
        passing: wsState.progress.passing,
        total: wsState.progress.total,
        percentage: wsState.progress.percentage,
      }
    }

    const total =
      (features?.pending.length ?? 0) +
      (features?.in_progress.length ?? 0) +
      (features?.done.length ?? 0) +
      (features?.needs_human_input?.length ?? 0)
    const passing = features?.done.length ?? 0
    const percentage = total > 0 ? Math.round((passing / total) * 100 * 10) / 10 : 0

    return { passing, total, percentage }
  }, [wsState.progress, features])

  // ---- Graph data query ----
  const { data: graphData } = useQuery({
    queryKey: ['dependencyGraph', selectedProject],
    queryFn: () => getDependencyGraph(selectedProject!),
    enabled: !!selectedProject && activeView === 'graph',
    refetchInterval: 5000,
  })

  // ---- Graph node click handler ----
  const handleGraphNodeClick = useCallback((nodeId: number) => {
    const allFeatures = [
      ...(features?.pending ?? []),
      ...(features?.in_progress ?? []),
      ...(features?.done ?? []),
      ...(features?.needs_human_input ?? []),
    ]
    const feature = allFeatures.find(f => f.id === nodeId)
    if (feature) setSelectedFeature(feature)
  }, [features])

  // ---- Side-effects ----

  // Play sounds when features move between columns
  useFeatureSound(features)

  // Celebrate when all features are complete
  useCelebration(features, selectedProject)

  // Validate stored project exists (clear if project was deleted)
  useEffect(() => {
    if (selectedProject && projects && !projects.some(p => p.name === selectedProject)) {
      setSelectedProject(null)
    }
  }, [selectedProject, projects, setSelectedProject])

  // ---- Keyboard shortcuts ----
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Skip if the user is typing in an input or textarea
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) {
        return
      }

      // -- View navigation shortcuts --

      if (e.key === 'h' || e.key === 'H') {
        e.preventDefault()
        setActiveView('dashboard')
        return
      }

      if (e.key === 'k' || e.key === 'K') {
        e.preventDefault()
        setActiveView('kanban')
        return
      }

      if (e.key === 'g' || e.key === 'G') {
        e.preventDefault()
        setActiveView('graph')
        return
      }

      if (e.key === 'b' || e.key === 'B') {
        e.preventDefault()
        setActiveView('browsers')
        return
      }

      if (e.key === 't' || e.key === 'T') {
        e.preventDefault()
        setActiveView('terminal')
        return
      }

      if (e.key === 'd' || e.key === 'D') {
        e.preventDefault()
        setActiveView('logs')
        return
      }

      // A : Toggle assistant panel (overlay, not view navigation)
      if ((e.key === 'a' || e.key === 'A') && selectedProject && !isSpecCreating) {
        e.preventDefault()
        setAssistantOpen(prev => !prev)
        return
      }

      // [ : Toggle sidebar
      if (e.key === '[') {
        e.preventDefault()
        toggleSidebar()
        return
      }

      // -- Modal shortcuts --

      // N : Add new feature (when project selected)
      if ((e.key === 'n' || e.key === 'N') && selectedProject) {
        e.preventDefault()
        setShowAddFeature(true)
        return
      }

      // E : Expand project with AI (when project selected, has spec, and has features)
      if (
        (e.key === 'e' || e.key === 'E') &&
        selectedProject &&
        hasSpec &&
        features &&
        (features.pending.length +
          features.in_progress.length +
          features.done.length +
          (features.needs_human_input?.length || 0)) > 0
      ) {
        e.preventDefault()
        setShowExpandProject(true)
        return
      }

      // , : Navigate to settings view
      if (e.key === ',') {
        e.preventDefault()
        setActiveView('settings')
        return
      }

      // ? : Show keyboard shortcuts help
      if (e.key === '?') {
        e.preventDefault()
        setShowKeyboardHelp(true)
        return
      }

      // R : Open reset modal (when project selected and agent not running/draining)
      if (
        (e.key === 'r' || e.key === 'R') &&
        selectedProject &&
        !['running', 'pausing', 'paused_graceful'].includes(wsState.agentStatus)
      ) {
        e.preventDefault()
        setShowResetModal(true)
        return
      }

      // Escape : Close modals in priority order
      if (e.key === 'Escape') {
        if (showKeyboardHelp) {
          setShowKeyboardHelp(false)
        } else if (showResetModal) {
          setShowResetModal(false)
        } else if (showExpandProject) {
          setShowExpandProject(false)
        } else if (showSettings) {
          setShowSettings(false)
        } else if (assistantOpen) {
          setAssistantOpen(false)
        } else if (showAddFeature) {
          setShowAddFeature(false)
        } else if (selectedFeature) {
          setSelectedFeature(null)
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [
    selectedProject,
    showAddFeature,
    showExpandProject,
    selectedFeature,
    assistantOpen,
    features,
    showSettings,
    showKeyboardHelp,
    isSpecCreating,
    showResetModal,
    wsState.agentStatus,
    hasSpec,
    setActiveView,
    toggleSidebar,
  ])

  // ---- Assemble context value (memoised to avoid unnecessary re-renders) ----
  const value = useMemo<AppContextValue>(
    () => ({
      // Project
      selectedProject,
      setSelectedProject,

      // View navigation
      activeView,
      setActiveView,

      // Sidebar
      sidebarCollapsed,
      setSidebarCollapsed,
      toggleSidebar,

      // Modals
      showAddFeature,
      setShowAddFeature,
      showExpandProject,
      setShowExpandProject,
      selectedFeature,
      setSelectedFeature,
      showSettings,
      setShowSettings,
      showKeyboardHelp,
      setShowKeyboardHelp,
      showResetModal,
      setShowResetModal,
      showSpecChat,
      setShowSpecChat,
      isSpecCreating,
      setIsSpecCreating,
      assistantOpen,
      setAssistantOpen,

      // Setup
      setupComplete,
      setSetupComplete,

      // Spec initializer
      specInitializerStatus,
      setSpecInitializerStatus,
      specInitializerError,
      setSpecInitializerError,

      // Queries / data
      projects,
      projectsLoading,
      features,
      settings,
      wsState,
      theme,
      setTheme,
      darkMode,
      toggleDarkMode,
      themes,
      currentTheme,
      queryClient,

      // Derived
      selectedProjectData,
      hasSpec,
      progress,

      // Graph
      graphData,
      handleGraphNodeClick,
    }),
    [
      selectedProject,
      setSelectedProject,
      activeView,
      setActiveView,
      sidebarCollapsed,
      setSidebarCollapsed,
      toggleSidebar,
      showAddFeature,
      showExpandProject,
      selectedFeature,
      showSettings,
      showKeyboardHelp,
      showResetModal,
      showSpecChat,
      isSpecCreating,
      assistantOpen,
      setupComplete,
      specInitializerStatus,
      specInitializerError,
      projects,
      projectsLoading,
      features,
      settings,
      wsState,
      theme,
      setTheme,
      darkMode,
      toggleDarkMode,
      themes,
      currentTheme,
      queryClient,
      selectedProjectData,
      hasSpec,
      progress,
      graphData,
      handleGraphNodeClick,
    ],
  )

  return (
    <AppContext.Provider value={value}>
      <TooltipProvider>
        {children}
      </TooltipProvider>
    </AppContext.Provider>
  )
}

// ---------------------------------------------------------------------------
// Consumer hook
// ---------------------------------------------------------------------------

/**
 * Access the global application context.
 * Must be called inside `<AppProvider>`.
 */
export function useAppContext(): AppContextValue {
  const ctx = useContext(AppContext)
  if (!ctx) {
    throw new Error('useAppContext must be used within an <AppProvider>')
  }
  return ctx
}
