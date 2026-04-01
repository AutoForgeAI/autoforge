import { useAppContext } from '@/contexts/AppContext'
import { AgentControl } from '../AgentControl'
import { DevServerControl } from '../DevServerControl'
import { RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'

/**
 * Compact horizontal control bar at the top of the content area.
 * Houses agent controls, dev server controls, mode badges, and reset.
 * Sticky within the scrollable content region.
 */
export function ControlBar() {
  const {
    selectedProject,
    selectedProjectData,
    wsState,
    settings,
    setShowResetModal,
  } = useAppContext()

  return (
    <div className="sticky top-0 z-20 w-full flex items-center gap-3 bg-card/80 backdrop-blur-md border-b border-border px-4 py-2 shrink-0">
      <AgentControl
        projectName={selectedProject!}
        status={wsState.agentStatus}
        defaultConcurrency={selectedProjectData?.default_concurrency}
      />

      <DevServerControl
        projectName={selectedProject!}
        status={wsState.devServerStatus}
        url={wsState.devServerUrl}
      />

      <div className="flex-1" />

      {settings?.ollama_mode && (
        <div className="hidden sm:flex items-center gap-1.5 px-2 py-1 bg-card rounded-lg border border-border shadow-sm">
          <img src="/ollama.png" alt="Ollama" className="w-4 h-4" />
          <span className="text-[11px] font-bold text-foreground">Ollama</span>
        </div>
      )}

      {settings?.glm_mode && (
        <Badge className="hidden sm:inline-flex bg-purple-500 text-white hover:bg-purple-600 text-[11px]">
          GLM
        </Badge>
      )}

      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            onClick={() => setShowResetModal(true)}
            variant="outline"
            size="sm"
            disabled={['running', 'pausing', 'paused_graceful'].includes(wsState.agentStatus)}
            className="h-8"
          >
            <RotateCcw size={16} />
          </Button>
        </TooltipTrigger>
        <TooltipContent>Reset (R)</TooltipContent>
      </Tooltip>
    </div>
  )
}
