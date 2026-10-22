/**
 * Kanban View
 *
 * Full-page kanban board for managing features across columns
 * (pending, in progress, done, needs human input).
 */

import { useAppContext } from '@/contexts/AppContext'
import { useAuth } from '@/hooks/useProjects'
import { KanbanBoard } from '../KanbanBoard'

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
  const { canEdit } = useAuth()
  const editable = canEdit(selectedProject)

  return (
    <div className="overflow-y-auto flex-1 p-6">
      <KanbanBoard
        features={features}
        onFeatureClick={setSelectedFeature}
        onAddFeature={editable ? () => setShowAddFeature(true) : undefined}
        onExpandProject={editable ? () => setShowExpandProject(true) : undefined}
        activeAgents={wsState.activeAgents}
        onCreateSpec={editable ? () => setShowSpecChat(true) : undefined}
        hasSpec={hasSpec}
      />
    </div>
  )
}
