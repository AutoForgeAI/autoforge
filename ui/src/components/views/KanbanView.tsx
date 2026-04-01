/**
 * Kanban View
 *
 * Full-page kanban board for managing features across columns
 * (pending, in progress, done, needs human input).
 */

import { useAppContext } from '@/contexts/AppContext'
import { KanbanBoard } from '../KanbanBoard'

export function KanbanView() {
  const {
    features,
    hasSpec,
    wsState,
    setSelectedFeature,
    setShowAddFeature,
    setShowExpandProject,
    setShowSpecChat,
  } = useAppContext()

  return (
    <div className="overflow-y-auto flex-1 p-6">
      <KanbanBoard
        features={features}
        onFeatureClick={setSelectedFeature}
        onAddFeature={() => setShowAddFeature(true)}
        onExpandProject={() => setShowExpandProject(true)}
        activeAgents={wsState.activeAgents}
        onCreateSpec={() => setShowSpecChat(true)}
        hasSpec={hasSpec}
      />
    </div>
  )
}
