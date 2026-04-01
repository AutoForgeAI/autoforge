/**
 * Graph View
 *
 * Full-page dependency graph visualization.
 * Shows feature nodes and their dependency edges using dagre layout.
 * Falls back to a loading spinner when graph data is not yet available.
 */

import { useAppContext } from '@/contexts/AppContext'
import { DependencyGraph } from '../DependencyGraph'
import { Loader2 } from 'lucide-react'

export function GraphView() {
  const { graphData, handleGraphNodeClick, wsState } = useAppContext()

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-hidden p-6">
      {graphData ? (
        <div className="flex-1 min-h-0">
          <DependencyGraph
            graphData={graphData}
            onNodeClick={handleGraphNodeClick}
            activeAgents={wsState.activeAgents}
          />
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center">
          <Loader2 size={32} className="animate-spin text-primary" />
        </div>
      )}
    </div>
  )
}
