import { useAppContext } from '@/contexts/AppContext'
import { AgentControl } from '../AgentControl'
import { DevServerControl } from '../DevServerControl'
import { DeniedCommandsDialog } from '../DeniedCommandsDialog'
import { useDeniedCommands } from '@/hooks/useProjects'
import { useState } from 'react'
import { RotateCcw, ShieldAlert } from 'lucide-react'
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

  const [showDenied, setShowDenied] = useState(false)
  // Poll while the agent is active so newly denied commands show up promptly
  const agentActive = ['running', 'pausing', 'paused_graceful'].includes(wsState.agentStatus)
  const { data: denied } = useDeniedCommands(selectedProject, agentActive ? 15_000 : false)
  const deniedCount = denied?.commands.filter(c => !c.currently_allowed).length ?? 0

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
            onClick={() => setShowDenied(true)}
            variant="outline"
            size="sm"
            className="h-8 relative"
            aria-label={`Denied commands${deniedCount > 0 ? ` (${deniedCount})` : ''}`}
          >
            <ShieldAlert size={16} />
            {deniedCount > 0 && (
              <span className="text-[11px] font-bold">{deniedCount}</span>
            )}
          </Button>
        </TooltipTrigger>
        <TooltipContent>Denied commands</TooltipContent>
      </Tooltip>

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

      <DeniedCommandsDialog
        isOpen={showDenied}
        projectName={selectedProject!}
        onClose={() => setShowDenied(false)}
      />
    </div>
  )
}
