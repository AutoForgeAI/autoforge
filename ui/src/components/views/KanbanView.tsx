/**
 * Kanban View
 *
 * Full-page kanban board for managing features across columns
 * (pending, in progress, done, needs human input).
 */

import { useState } from 'react'
import { useAppContext } from '@/contexts/AppContext'
import { KanbanBoard } from '../KanbanBoard'
import { GitHubImportModal } from '../GitHubImportModal'

export function KanbanView() {
  const {
    selectedProject,
    features,
    hasSpec,
    wsState,
    setSelectedFeature,
    setShowAddFeature,
    setShowExpandProject,
    setShowSpecChat,
  } = useAppContext()
  const [showGitHubImport, setShowGitHubImport] = useState(false)

  return (
    <div className="overflow-y-auto flex-1 p-6">
      <KanbanBoard
        features={features}
        onFeatureClick={setSelectedFeature}
        onAddFeature={() => setShowAddFeature(true)}
        onExpandProject={() => setShowExpandProject(true)}
        onImportGitHub={selectedProject ? () => setShowGitHubImport(true) : undefined}
        activeAgents={wsState.activeAgents}
        onCreateSpec={() => setShowSpecChat(true)}
        hasSpec={hasSpec}
      />
      {showGitHubImport && selectedProject && (
        <GitHubImportModal
          projectName={selectedProject}
          onClose={() => setShowGitHubImport(false)}
        />
      )}
    </div>
  )
}
