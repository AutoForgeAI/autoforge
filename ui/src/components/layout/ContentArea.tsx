/**
 * Content Area - View Router
 *
 * Renders the active view based on the current `activeView` state from AppContext.
 * Also handles pre-conditions: setup wizard, project selection, and spec creation.
 */

import { useAppContext } from '@/contexts/AppContext'
import { SetupWizard } from '../SetupWizard'
import { ProjectSetupRequired } from '../ProjectSetupRequired'
import { DashboardView } from '../views/DashboardView'
import { KanbanView } from '../views/KanbanView'
import { GraphView } from '../views/GraphView'
import { BrowsersView } from '../views/BrowsersView'
import { TerminalView } from '../views/TerminalView'
import { LogsView } from '../views/LogsView'
import { AssistantView } from '../views/AssistantView'
import { SettingsView } from '../views/SettingsView'

export function ContentArea() {
  const {
    selectedProject,
    hasSpec,
    setupComplete,
    setSetupComplete,
    setShowSpecChat,
    activeView,
    selectedProjectData,
  } = useAppContext()

  // Step 1: First-run setup wizard
  if (!setupComplete) {
    return <SetupWizard onComplete={() => setSetupComplete(true)} />
  }

  // Settings is always accessible regardless of project state
  if (activeView === 'settings') {
    return <SettingsView />
  }

  // Step 2: No project selected - show welcome message
  if (!selectedProject) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <h2 className="font-display text-2xl font-bold mb-2">Welcome to AutoForge</h2>
          <p className="text-muted-foreground">Select a project from the sidebar to get started.</p>
        </div>
      </div>
    )
  }

  // Step 3: Project exists but has no spec - prompt user to create one
  if (!hasSpec) {
    return (
      <div className="flex-1 overflow-y-auto p-6">
        <ProjectSetupRequired
          projectName={selectedProject}
          projectPath={selectedProjectData?.path}
          onCreateWithClaude={() => setShowSpecChat(true)}
          onEditManually={() => {
            /* Could navigate to terminal view */
          }}
        />
      </div>
    )
  }

  // Step 4: Render the active view
  switch (activeView) {
    case 'dashboard':
      return <DashboardView />
    case 'kanban':
      return <KanbanView />
    case 'graph':
      return <GraphView />
    case 'browsers':
      return <BrowsersView />
    case 'terminal':
      return <TerminalView />
    case 'logs':
      return <LogsView />
    case 'assistant':
      return <AssistantView />
    default:
      return <DashboardView />
  }
}
