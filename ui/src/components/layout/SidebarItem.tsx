import { type LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Tooltip, TooltipTrigger, TooltipContent } from '@/components/ui/tooltip'
import { Badge } from '@/components/ui/badge'

interface SidebarItemProps {
  icon: LucideIcon
  label: string
  isActive: boolean
  isCollapsed: boolean
  onClick: () => void
  badge?: number | string
  shortcutKey?: string
}

/**
 * A single sidebar navigation item that adapts between collapsed (icon-only)
 * and expanded (icon + label + optional badge/shortcut) states.
 *
 * Active state uses a subtle left-edge accent line and primary background.
 * Hover state applies a gentle lift and background shift for tactile feedback.
 */
export function SidebarItem({
  icon: Icon,
  label,
  isActive,
  isCollapsed,
  onClick,
  badge,
  shortcutKey,
}: SidebarItemProps) {
  const button = (
    <button
      onClick={onClick}
      aria-label={label}
      className={cn(
        // Base layout
        'group relative flex items-center rounded-lg w-full',
        'transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)]',
        'outline-none focus-visible:ring-2 focus-visible:ring-sidebar-ring',

        // Active state: vivid primary with left accent stripe
        isActive && [
          'bg-sidebar-primary text-sidebar-primary-foreground',
          'shadow-sm',
        ],

        // Inactive: subtle hover lift
        !isActive && [
          'text-sidebar-foreground/70',
          'hover:bg-sidebar-accent hover:text-sidebar-accent-foreground',
          'hover:shadow-sm',
          'active:scale-[0.98]',
        ],

        // Sizing
        isCollapsed ? 'h-11 w-11 justify-center mx-auto' : 'h-9 px-3 gap-3',
      )}
    >
      {/* Left accent bar for active state (expanded only) */}
      {isActive && !isCollapsed && (
        <span
          className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r-full bg-sidebar-primary-foreground/40"
        />
      )}

      {/* Icon with subtle scale on active */}
      <Icon
        size={isCollapsed ? 20 : 18}
        className={cn(
          'shrink-0 transition-transform duration-200',
          isActive && 'scale-110',
          !isActive && 'group-hover:translate-x-0.5',
        )}
      />

      {/* Label and accessories — expanded mode only */}
      {!isCollapsed && (
        <>
          <span className="truncate text-sm font-medium flex-1 text-left">
            {label}
          </span>

          {badge !== undefined && (
            <Badge
              variant="secondary"
              className={cn(
                'text-[10px] px-1.5 py-0 h-5 min-w-5 tabular-nums',
                'transition-opacity duration-200',
                isActive && 'bg-sidebar-primary-foreground/20 text-sidebar-primary-foreground',
              )}
            >
              {badge}
            </Badge>
          )}

          {shortcutKey && badge === undefined && (
            <kbd
              className={cn(
                'text-[10px] font-mono leading-none px-1 py-0.5 rounded',
                'opacity-0 group-hover:opacity-100 transition-opacity duration-200',
                isActive
                  ? 'text-sidebar-primary-foreground/50'
                  : 'text-muted-foreground/60 bg-sidebar-accent/50',
              )}
            >
              {shortcutKey}
            </kbd>
          )}
        </>
      )}
    </button>
  )

  // In collapsed mode, wrap with a tooltip so the label is discoverable
  if (isCollapsed) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>{button}</TooltipTrigger>
        <TooltipContent side="right" sideOffset={8} className="font-medium">
          {label}
          {shortcutKey && (
            <kbd className="ml-2 text-[10px] font-mono opacity-60">{shortcutKey}</kbd>
          )}
        </TooltipContent>
      </Tooltip>
    )
  }

  return button
}
