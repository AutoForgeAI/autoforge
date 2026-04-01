import { useAppContext } from '@/contexts/AppContext'
import { Sidebar } from './Sidebar'
import { ControlBar } from './ControlBar'
import { ContentArea } from './ContentArea'

/**
 * Top-level layout component that composes the three structural regions:
 *   Sidebar  |  ControlBar + ContentArea
 *
 * The sidebar sits on the left. The right column stacks the ControlBar
 * (shown only when a project is selected) above the scrollable ContentArea.
 */
export function AppShell() {
  const { selectedProject } = useAppContext()

  return (
    <div className="flex h-screen overflow-hidden bg-background">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {selectedProject && <ControlBar />}
        <ContentArea />
      </div>
    </div>
  )
}
