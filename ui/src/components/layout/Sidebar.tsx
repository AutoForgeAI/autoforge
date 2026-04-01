import { useAppContext } from '@/contexts/AppContext'
import { SidebarItem } from './SidebarItem'
import { ProjectSelector } from '../ProjectSelector'
import {
  LayoutDashboard,
  Columns3,
  GitBranch,
  Monitor,
  Terminal,
  ScrollText,
  Bot,
  Settings,
  Moon,
  Sun,
  BookOpen,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

/**
 * Collapsible left sidebar for view navigation.
 *
 * Design approach: precision-engineered utility. Clean separation between
 * navigation groups, quiet bottom utility row, smooth width transitions.
 * All colours come from theme-aware --sidebar-* CSS variables.
 */
export function Sidebar() {
  const {
    activeView,
    setActiveView,
    sidebarCollapsed,
    toggleSidebar,
    selectedProject,
    projects,
    projectsLoading,
    setSelectedProject,
    darkMode,
    toggleDarkMode,
    wsState,
    setIsSpecCreating,
  } = useAppContext()

  const browserCount = wsState.browserScreenshots.size
  const logCount = wsState.logs.length

  return (
    <aside
      className={cn(
        'h-screen flex flex-col shrink-0 z-30 overflow-hidden',
        'bg-sidebar text-sidebar-foreground',
        'border-r border-sidebar-border',
        'transition-[width] duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]',
        sidebarCollapsed ? 'w-[64px]' : 'w-[240px]',
      )}
    >
      {/* ───────────────────────────────────────────────────────────────────
          Header: logo, title, project selector
          ─────────────────────────────────────────────────────────────────── */}
      <div className="flex-shrink-0 px-3 pt-4 pb-3">
        {/* Logo row */}
        <div
          className={cn(
            'flex items-center',
            sidebarCollapsed ? 'justify-center' : 'gap-2.5',
          )}
        >
          <img
            src="/logo.png"
            alt="AutoForge"
            className={cn(
              'rounded-full shrink-0 transition-all duration-200',
              sidebarCollapsed ? 'h-8 w-8' : 'h-7 w-7',
            )}
          />
          <div
            className={cn(
              'overflow-hidden transition-all duration-200',
              sidebarCollapsed ? 'w-0 opacity-0' : 'w-auto opacity-100',
            )}
          >
            <span className="font-bold text-base tracking-tight uppercase whitespace-nowrap block">
              AutoForge
            </span>
          </div>
        </div>

        {/* Project selector — hidden when collapsed */}
        <div
          className={cn(
            'overflow-hidden transition-all duration-200',
            sidebarCollapsed ? 'max-h-0 opacity-0 mt-0' : 'max-h-20 opacity-100 mt-3',
          )}
        >
          <ProjectSelector
            projects={projects ?? []}
            selectedProject={selectedProject}
            onSelectProject={setSelectedProject}
            isLoading={projectsLoading}
            onSpecCreatingChange={setIsSpecCreating}
          />
        </div>
      </div>

      {/* Subtle divider */}
      <div className="mx-3 h-px bg-sidebar-border" />

      {/* ───────────────────────────────────────────────────────────────────
          Navigation items
          ─────────────────────────────────────────────────────────────────── */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
        {selectedProject ? (
          <>
            {/* Section label (expanded only) */}
            {!sidebarCollapsed && (
              <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/40">
                Views
              </p>
            )}

            <SidebarItem
              icon={LayoutDashboard}
              label="Dashboard"
              isActive={activeView === 'dashboard'}
              isCollapsed={sidebarCollapsed}
              onClick={() => setActiveView('dashboard')}
              shortcutKey="H"
            />
            <SidebarItem
              icon={Columns3}
              label="Kanban"
              isActive={activeView === 'kanban'}
              isCollapsed={sidebarCollapsed}
              onClick={() => setActiveView('kanban')}
              shortcutKey="K"
            />
            <SidebarItem
              icon={GitBranch}
              label="Graph"
              isActive={activeView === 'graph'}
              isCollapsed={sidebarCollapsed}
              onClick={() => setActiveView('graph')}
              shortcutKey="G"
            />
            <SidebarItem
              icon={Monitor}
              label="Browsers"
              isActive={activeView === 'browsers'}
              isCollapsed={sidebarCollapsed}
              onClick={() => setActiveView('browsers')}
              shortcutKey="B"
              badge={browserCount > 0 ? browserCount : undefined}
            />

            {/* Divider between groups */}
            <div className="my-2 mx-2 h-px bg-sidebar-border/60" />

            {/* Section label */}
            {!sidebarCollapsed && (
              <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-sidebar-foreground/40">
                Tools
              </p>
            )}

            <SidebarItem
              icon={Terminal}
              label="Terminal"
              isActive={activeView === 'terminal'}
              isCollapsed={sidebarCollapsed}
              onClick={() => setActiveView('terminal')}
              shortcutKey="T"
            />
            <SidebarItem
              icon={ScrollText}
              label="Logs"
              isActive={activeView === 'logs'}
              isCollapsed={sidebarCollapsed}
              onClick={() => setActiveView('logs')}
              shortcutKey="D"
              badge={logCount > 0 ? logCount : undefined}
            />
            <SidebarItem
              icon={Bot}
              label="Assistant"
              isActive={activeView === 'assistant'}
              isCollapsed={sidebarCollapsed}
              onClick={() => setActiveView('assistant')}
              shortcutKey="A"
            />
          </>
        ) : (
          /* Prompt when no project selected */
          !sidebarCollapsed && (
            <div className="px-3 py-8 text-center">
              <p className="text-sm text-sidebar-foreground/40 leading-relaxed">
                Select a project to get started
              </p>
            </div>
          )
        )}
      </nav>

      {/* ───────────────────────────────────────────────────────────────────
          Bottom utility section
          ─────────────────────────────────────────────────────────────────── */}
      <div className="flex-shrink-0 mt-auto px-2 py-2.5 border-t border-sidebar-border/60">
        <div className={cn('flex flex-col', sidebarCollapsed ? 'items-center gap-1' : 'gap-0.5')}>
          {/* Settings - navigates to settings view */}
          <UtilityButton
            icon={Settings}
            label="Settings"
            shortcut=","
            collapsed={sidebarCollapsed}
            onClick={() => setActiveView('settings')}
          />

          {/* Dark mode toggle */}
          <UtilityButton
            icon={darkMode ? Sun : Moon}
            label={darkMode ? 'Light mode' : 'Dark mode'}
            collapsed={sidebarCollapsed}
            onClick={toggleDarkMode}
          />

          {/* Docs link */}
          <UtilityButton
            icon={BookOpen}
            label="Docs"
            collapsed={sidebarCollapsed}
            onClick={() => window.open('https://autoforge.cc', '_blank')}
          />

          {/* Collapse / expand toggle */}
          <div className={cn('mt-1 pt-1', !sidebarCollapsed && 'border-t border-sidebar-border/40')}>
            <UtilityButton
              icon={sidebarCollapsed ? PanelLeftOpen : PanelLeftClose}
              label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse'}
              shortcut="["
              collapsed={sidebarCollapsed}
              onClick={toggleSidebar}
            />
          </div>
        </div>
      </div>
    </aside>
  )
}

/* ─────────────────────────────────────────────────────────────────────────────
   Small utility button used in the bottom section.
   Separated to keep the main component readable.
   ───────────────────────────────────────────────────────────────────────────── */

function UtilityButton({
  icon: Icon,
  label,
  shortcut,
  collapsed,
  onClick,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>
  label: string
  shortcut?: string
  collapsed: boolean
  onClick: () => void
}) {
  if (collapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClick}
            aria-label={label}
            className="h-8 w-8 text-sidebar-foreground/60 hover:text-sidebar-foreground hover:bg-sidebar-accent transition-colors duration-150"
          >
            <Icon size={16} />
          </Button>
        </TooltipTrigger>
        <TooltipContent side="right" sideOffset={8}>
          {label}
          {shortcut && <kbd className="ml-2 text-[10px] font-mono opacity-60">{shortcut}</kbd>}
        </TooltipContent>
      </Tooltip>
    )
  }

  return (
    <button
      onClick={onClick}
      className={cn(
        'group flex items-center gap-3 w-full h-8 px-3 rounded-lg text-sm',
        'text-sidebar-foreground/60 hover:text-sidebar-foreground',
        'hover:bg-sidebar-accent transition-all duration-150',
        'active:scale-[0.98]',
      )}
    >
      <Icon size={16} className="shrink-0" />
      <span className="flex-1 text-left truncate text-[13px]">{label}</span>
      {shortcut && (
        <kbd className="text-[10px] font-mono opacity-0 group-hover:opacity-60 transition-opacity duration-200">
          {shortcut}
        </kbd>
      )}
    </button>
  )
}
