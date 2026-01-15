import { Folder, ChevronRight, BarChart3, Clock, CheckCircle2 } from 'lucide-react'
import type { ProjectSummary } from '../lib/types'

interface ProjectGridProps {
  projects: ProjectSummary[]
  onProjectClick: (project: ProjectSummary) => void
  isLoading?: boolean
}

function ProjectCard({ project, onClick }: { project: ProjectSummary; onClick: () => void }) {
  const { stats } = project
  const percentage = stats?.percentage ?? 0
  const isComplete = percentage === 100
  const hasProgress = percentage > 0

  return (
    <button
      onClick={onClick}
      className="neo-card p-4 text-left group hover:border-[var(--color-neo-accent)] transition-colors"
    >
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <div className={`
            p-2 rounded-lg
            ${isComplete ? 'bg-green-100 text-green-600' : 'bg-[var(--color-neo-bg)]'}
          `}>
            <Folder size={20} />
          </div>
          <div>
            <h3 className="font-display font-bold line-clamp-1">{project.name}</h3>
            {project.path && (
              <p className="text-xs text-[var(--color-neo-text-secondary)] line-clamp-1 font-mono">
                {project.path}
              </p>
            )}
          </div>
        </div>
        <ChevronRight
          size={20}
          className="text-[var(--color-neo-text-secondary)] group-hover:translate-x-1 transition-transform"
        />
      </div>

      {/* Progress Bar */}
      <div className="mb-3">
        <div className="flex items-center justify-between text-sm mb-1">
          <span className="text-[var(--color-neo-text-secondary)]">Progress</span>
          <span className="font-bold">{percentage.toFixed(1)}%</span>
        </div>
        <div className="h-2 bg-[var(--color-neo-border)] rounded-full overflow-hidden">
          <div
            className="h-full rounded-full transition-all duration-500"
            style={{
              width: `${percentage}%`,
              backgroundColor: isComplete
                ? 'var(--color-neo-done)'
                : hasProgress
                  ? 'var(--color-neo-progress)'
                  : 'var(--color-neo-pending)',
            }}
          />
        </div>
      </div>

      {/* Stats */}
      <div className="flex items-center gap-4 text-xs text-[var(--color-neo-text-secondary)]">
        <div className="flex items-center gap-1">
          <BarChart3 size={12} />
          <span>{stats?.total ?? 0} tasks</span>
        </div>
        {stats?.in_progress > 0 && (
          <div className="flex items-center gap-1 text-[var(--color-neo-progress)]">
            <Clock size={12} />
            <span>{stats.in_progress} in progress</span>
          </div>
        )}
        {isComplete && (
          <div className="flex items-center gap-1 text-[var(--color-neo-done)]">
            <CheckCircle2 size={12} />
            <span>Complete</span>
          </div>
        )}
      </div>

      {/* Spec Status */}
      {!project.has_spec && (
        <div className="mt-2 text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded">
          No app spec configured
        </div>
      )}
    </button>
  )
}

export function ProjectGrid({ projects, onProjectClick, isLoading }: ProjectGridProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="neo-card p-4 animate-pulse">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-10 h-10 bg-[var(--color-neo-border)] rounded-lg" />
              <div className="flex-1">
                <div className="h-4 bg-[var(--color-neo-border)] rounded w-3/4 mb-1" />
                <div className="h-3 bg-[var(--color-neo-border)] rounded w-1/2" />
              </div>
            </div>
            <div className="h-2 bg-[var(--color-neo-border)] rounded-full mb-3" />
            <div className="flex gap-4">
              <div className="h-3 bg-[var(--color-neo-border)] rounded w-16" />
              <div className="h-3 bg-[var(--color-neo-border)] rounded w-20" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (projects.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <Folder size={48} className="text-[var(--color-neo-text-secondary)] mb-4" />
        <h3 className="font-display font-bold text-lg mb-2">No Projects Yet</h3>
        <p className="text-[var(--color-neo-text-secondary)] max-w-md">
          Create your first project to get started with autonomous coding.
        </p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 p-4">
      {projects.map(project => (
        <ProjectCard
          key={project.name}
          project={project}
          onClick={() => onProjectClick(project)}
        />
      ))}
    </div>
  )
}
