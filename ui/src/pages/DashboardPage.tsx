import { useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, FolderOpen, Plus, Search, Settings as SettingsIcon } from 'lucide-react'
import type { ProjectSummary, SetupStatus } from '../lib/types'

type SetupRow = {
  key: keyof SetupStatus
  label: string
  optional?: boolean
}

const SETUP_ROWS: SetupRow[] = [
  { key: 'claude_cli', label: 'Claude CLI' },
  { key: 'credentials', label: 'Credentials' },
  { key: 'node', label: 'Node' },
  { key: 'npm', label: 'npm' },
  { key: 'codex_cli', label: 'Codex CLI', optional: true },
  { key: 'gemini_cli', label: 'Gemini CLI', optional: true },
]

interface DashboardPageProps {
  projects: ProjectSummary[]
  isLoading: boolean
  setupStatus?: SetupStatus
  backgroundRunProject: string | null
  onOpenProject: (projectName: string) => void
  onManageProject: (projectName: string) => void
  onDismissBackgroundRun: () => void
  onNewProject: () => void
  onOpenSettings: () => void
}

export function DashboardPage({
  projects,
  isLoading,
  setupStatus,
  backgroundRunProject,
  onOpenProject,
  onManageProject,
  onDismissBackgroundRun,
  onNewProject,
  onOpenSettings,
}: DashboardPageProps) {
  const [query, setQuery] = useState('')

  const filteredProjects = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return projects
    return projects.filter((p) => p.name.toLowerCase().includes(q) || p.path.toLowerCase().includes(q))
  }, [projects, query])

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1">
          <h1 className="font-display text-3xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-[var(--color-neo-text-secondary)]">
            Pick a project to continue, or create a new one.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            className="neo-btn neo-btn-primary text-sm flex items-center gap-2"
            onClick={onNewProject}
          >
            <Plus size={18} />
            New Project
            <kbd className="hidden md:inline ml-1.5 px-1.5 py-0.5 text-xs bg-black/20 rounded font-mono">
              N
            </kbd>
          </button>
          <button
            type="button"
            className="neo-btn neo-btn-secondary text-sm flex items-center gap-2"
            onClick={onOpenSettings}
            title="Global settings"
          >
            <SettingsIcon size={18} />
            Settings
            <kbd className="hidden md:inline ml-1.5 px-1.5 py-0.5 text-xs bg-black/10 rounded font-mono">
              S
            </kbd>
          </button>
        </div>
      </div>

      {backgroundRunProject && (
        <div className="neo-card p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="inline-flex w-2.5 h-2.5 rounded-full bg-[var(--color-neo-progress)] shadow-neo-sm" />
            <div className="text-sm">
              <div className="font-display font-semibold">Still running in the background</div>
              <div className="text-[var(--color-neo-text-secondary)]">{backgroundRunProject}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="neo-btn neo-btn-sm bg-[var(--color-neo-progress)] text-[var(--color-neo-text-on-bright)]"
              onClick={() => onOpenProject(backgroundRunProject)}
              title="Open project"
            >
              Open
            </button>
            <button
              type="button"
              className="neo-btn neo-btn-sm bg-[var(--color-neo-bg)]"
              onClick={onDismissBackgroundRun}
              title="Dismiss"
            >
              Dismiss
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Projects */}
        <div className="neo-card p-6 lg:col-span-2 space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2">
              <FolderOpen size={18} />
              <div className="font-display text-lg font-semibold">Projects</div>
              <span className="neo-badge bg-[var(--color-neo-bg)]">{projects.length}</span>
            </div>

            <div className="relative w-full sm:w-[280px]">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-neo-text-secondary)]" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search projects…"
                className="neo-input w-full pl-9"
              />
            </div>
          </div>

          {isLoading ? (
            <div className="neo-card neo-card-flat p-6 text-sm text-[var(--color-neo-text-secondary)]">
              Loading projects…
            </div>
          ) : projects.length === 0 ? (
            <div className="neo-card neo-card-flat p-6">
              <div className="font-display font-semibold mb-1">No projects yet</div>
              <div className="text-sm text-[var(--color-neo-text-secondary)]">
                Create your first project to start generating features.
              </div>
            </div>
          ) : filteredProjects.length === 0 ? (
            <div className="neo-card neo-card-flat p-6 text-sm text-[var(--color-neo-text-secondary)]">
              No matches. Try a different search.
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {filteredProjects.slice(0, 8).map((project) => {
                const needsSetup = project.setup_required ?? !project.has_spec
                const hasStats = project.stats.total > 0
                const pct = Math.max(0, Math.min(100, project.stats.percentage))

                return (
                  <div
                    key={project.name}
                    className="neo-card neo-card-flat p-4 text-left hover:bg-[var(--color-neo-hover-subtle)] transition-colors"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="font-display font-semibold truncate">{project.name}</div>
                        <div className="text-xs text-[var(--color-neo-text-secondary)] font-mono truncate">
                          {project.path}
                        </div>
                      </div>

                      <div className="flex flex-col items-end gap-1">
                        <span
                          className={`neo-badge ${
                            needsSetup
                              ? 'bg-[var(--color-neo-pending)] text-[var(--color-neo-text-on-bright)]'
                              : 'bg-[var(--color-neo-done)] text-[var(--color-neo-text-on-bright)]'
                          }`}
                        >
                          {needsSetup ? 'Setup' : 'Ready'}
                        </span>
                        {hasStats && (
                          <span className="text-xs font-mono text-[var(--color-neo-text-secondary)]">
                            {project.stats.passing}/{project.stats.total}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="mt-3 space-y-1">
                      <div className="flex items-center justify-between text-xs text-[var(--color-neo-text-secondary)]">
                        <span>Progress</span>
                        <span className="font-mono">{hasStats ? `${pct}%` : '—'}</span>
                      </div>
                      <div className="h-2 w-full bg-[var(--color-neo-neutral-200)] rounded">
                        <div
                          className="h-2 bg-[var(--color-neo-progress)] rounded"
                          style={{ width: hasStats ? `${pct}%` : '0%' }}
                        />
                      </div>
                    </div>

                    <div className="mt-4 flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        className="neo-btn neo-btn-primary text-xs"
                        onClick={() => onOpenProject(project.name)}
                      >
                        Open
                      </button>
                      <button
                        type="button"
                        className="neo-btn neo-btn-secondary text-xs"
                        onClick={() => onManageProject(project.name)}
                      >
                        Manage
                      </button>
                      <span className="text-xs text-[var(--color-neo-text-secondary)]">
                        Reset/Delete inside Settings → Config
                      </span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {filteredProjects.length > 8 && (
            <div className="text-xs text-[var(--color-neo-text-secondary)]">
              Showing 8 of {filteredProjects.length}. Use search to narrow it down.
            </div>
          )}
        </div>

        {/* Side rail */}
        <div className="space-y-6">
          <div className="neo-card p-6 space-y-3">
            <div className="font-display text-lg font-semibold">System Status</div>

            {!setupStatus ? (
              <div className="text-sm text-[var(--color-neo-text-secondary)]">Checking environment…</div>
            ) : (
              <div className="space-y-2">
                {SETUP_ROWS.filter((row) => !row.optional || row.key in setupStatus).map((row) => {
                  const ok = Boolean(setupStatus[row.key])
                  return (
                    <div key={row.key} className="flex items-center justify-between gap-3 text-sm">
                      <div className="flex items-center gap-2">
                        {ok ? (
                          <CheckCircle2 size={16} className="text-[var(--color-neo-done)]" />
                        ) : (
                          <AlertTriangle size={16} className="text-[var(--color-neo-pending)]" />
                        )}
                        <span>{row.label}</span>
                      </div>
                      <span
                        className={`text-xs font-mono ${
                          ok ? 'text-[var(--color-neo-done)]' : 'text-[var(--color-neo-text-secondary)]'
                        }`}
                      >
                        {ok ? 'OK' : 'Missing'}
                      </span>
                    </div>
                  )
                })}
              </div>
            )}

            <div className="text-xs text-[var(--color-neo-text-secondary)]">
              Fix missing items in your environment and refresh the page.
            </div>
          </div>

          <div className="neo-card p-6 space-y-3">
            <div className="font-display text-lg font-semibold">Shortcuts</div>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div className="flex items-center justify-between gap-2">
                <span>New Project</span>
                <kbd className="px-1.5 py-0.5 text-xs bg-[var(--color-neo-bg)] rounded font-mono border border-[var(--color-neo-border)]">
                  N
                </kbd>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span>Logs</span>
                <kbd className="px-1.5 py-0.5 text-xs bg-[var(--color-neo-bg)] rounded font-mono border border-[var(--color-neo-border)]">
                  D
                </kbd>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span>Expand</span>
                <kbd className="px-1.5 py-0.5 text-xs bg-[var(--color-neo-bg)] rounded font-mono border border-[var(--color-neo-border)]">
                  E
                </kbd>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span>Mission Control</span>
                <kbd className="px-1.5 py-0.5 text-xs bg-[var(--color-neo-bg)] rounded font-mono border border-[var(--color-neo-border)]">
                  M
                </kbd>
              </div>
            </div>
            <div className="text-xs text-[var(--color-neo-text-secondary)]">
              Shortcuts depend on context (Dashboard vs Project).
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
