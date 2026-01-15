import { ChevronRight, Home } from 'lucide-react'

export interface BreadcrumbItem {
  label: string
  href?: string
  onClick?: () => void
  icon?: React.ReactNode
}

interface BreadcrumbProps {
  items: BreadcrumbItem[]
  separator?: React.ReactNode
}

export function Breadcrumb({
  items,
  separator = <ChevronRight size={14} className="text-[var(--color-neo-text-secondary)]" />,
}: BreadcrumbProps) {
  if (items.length === 0) return null

  return (
    <nav
      aria-label="Breadcrumb"
      className="flex items-center gap-1 text-sm overflow-x-auto"
    >
      {items.map((item, index) => {
        const isLast = index === items.length - 1
        const isClickable = !isLast && (item.href || item.onClick)

        return (
          <div key={index} className="flex items-center gap-1 min-w-0">
            {index > 0 && <span className="flex-shrink-0">{separator}</span>}

            {isClickable ? (
              <button
                onClick={item.onClick}
                className="flex items-center gap-1 px-2 py-1 rounded hover:bg-[var(--color-neo-bg)] transition-colors truncate max-w-[200px]"
              >
                {item.icon && <span className="flex-shrink-0">{item.icon}</span>}
                <span className="truncate">{item.label}</span>
              </button>
            ) : (
              <span
                className={`
                  flex items-center gap-1 px-2 py-1 truncate max-w-[200px]
                  ${isLast ? 'font-bold' : 'text-[var(--color-neo-text-secondary)]'}
                `}
              >
                {item.icon && <span className="flex-shrink-0">{item.icon}</span>}
                <span className="truncate">{item.label}</span>
              </span>
            )}
          </div>
        )
      })}
    </nav>
  )
}

// Convenience component for project drill-down navigation
interface ProjectBreadcrumbProps {
  projectName?: string
  phaseName?: string
  featureName?: string
  taskName?: string
  onNavigateHome?: () => void
  onNavigateProject?: () => void
  onNavigatePhase?: () => void
  onNavigateFeature?: () => void
}

export function ProjectBreadcrumb({
  projectName,
  phaseName,
  featureName,
  taskName,
  onNavigateHome,
  onNavigateProject,
  onNavigatePhase,
  onNavigateFeature,
}: ProjectBreadcrumbProps) {
  const items: BreadcrumbItem[] = [
    {
      label: 'Projects',
      icon: <Home size={14} />,
      onClick: onNavigateHome,
    },
  ]

  if (projectName) {
    items.push({
      label: projectName,
      onClick: onNavigateProject,
    })
  }

  if (phaseName) {
    items.push({
      label: phaseName,
      onClick: onNavigatePhase,
    })
  }

  if (featureName) {
    items.push({
      label: featureName,
      onClick: onNavigateFeature,
    })
  }

  if (taskName) {
    items.push({
      label: taskName,
    })
  }

  return <Breadcrumb items={items} />
}
