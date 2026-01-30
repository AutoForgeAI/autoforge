import { LayoutGrid, GitBranch, Columns4 } from 'lucide-react'
import { Button } from '@/components/ui/button'

export type ViewMode = 'kanban' | 'kanban4' | 'graph'

interface ViewToggleProps {
  viewMode: ViewMode
  onViewModeChange: (mode: ViewMode) => void
}

/**
 * Toggle button to switch between Kanban (3-col), Kanban (4-col), and Graph views
 */
export function ViewToggle({ viewMode, onViewModeChange }: ViewToggleProps) {
  return (
    <div className="inline-flex rounded-lg border p-1 bg-background">
      <Button
        variant={viewMode === 'kanban' ? 'default' : 'ghost'}
        size="sm"
        onClick={() => onViewModeChange('kanban')}
        title="Kanban View (3 columns)"
      >
        <LayoutGrid size={16} />
        Kanban
      </Button>
      <Button
        variant={viewMode === 'kanban4' ? 'default' : 'ghost'}
        size="sm"
        onClick={() => onViewModeChange('kanban4')}
        title="Kanban View (4 columns: Pending, In Progress, Testing, Complete)"
      >
        <Columns4 size={16} />
        4-Column
      </Button>
      <Button
        variant={viewMode === 'graph' ? 'default' : 'ghost'}
        size="sm"
        onClick={() => onViewModeChange('graph')}
        title="Dependency Graph View"
      >
        <GitBranch size={16} />
        Graph
      </Button>
    </div>
  )
}
