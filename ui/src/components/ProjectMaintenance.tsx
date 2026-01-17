import { useState } from 'react'
import { RotateCcw, Trash2, AlertTriangle } from 'lucide-react'
import { useDeleteProject, useResetProject } from '../hooks/useProjects'
import { ConfirmationDialog } from './ConfirmationDialog'

interface ProjectMaintenanceProps {
  projectName: string
}

export function ProjectMaintenance({ projectName }: ProjectMaintenanceProps) {
  const resetProject = useResetProject()
  const deleteProject = useDeleteProject()

  const [confirmReset, setConfirmReset] = useState(false)
  const [confirmFullReset, setConfirmFullReset] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleteFiles, setDeleteFiles] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleReset = async (fullReset: boolean) => {
    setError(null)
    setMessage(null)
    try {
      await resetProject.mutateAsync({ name: projectName, fullReset })
      setMessage(fullReset ? 'Full reset complete.' : 'Project reset complete.')
    } catch (e: any) {
      setError(String(e?.message || e))
    }
  }

  const handleDelete = async () => {
    setError(null)
    setMessage(null)
    try {
      await deleteProject.mutateAsync({ name: projectName, deleteFiles })
      setMessage('Project deleted.')
      window.location.hash = ''
    } catch (e: any) {
      setError(String(e?.message || e))
    }
  }

  return (
    <div className="neo-card p-4 border-4 border-[var(--color-neo-danger)]">
      <div className="flex items-start gap-3">
        <div className="p-2 bg-[var(--color-neo-danger)] border-3 border-[var(--color-neo-border)] shadow-[2px_2px_0px_rgba(0,0,0,1)]">
          <AlertTriangle size={18} className="text-white" />
        </div>
        <div>
          <div className="font-display font-bold uppercase">Danger zone</div>
          <div className="text-sm text-[var(--color-neo-text-secondary)]">
            Reset clears runtime state. Full reset also wipes prompts/specs. Delete removes the registry entry.
          </div>
        </div>
      </div>

      {message && (
        <div className="mt-3 neo-card p-3 border-3 border-[var(--color-neo-done)] text-sm">
          {message}
        </div>
      )}

      {error && (
        <div className="mt-3 neo-card p-3 border-3 border-[var(--color-neo-danger)] text-sm text-[var(--color-neo-danger)]">
          {error}
        </div>
      )}

      <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3">
        <div className="neo-card p-3">
          <div className="font-display font-bold uppercase text-sm mb-2">Reset runtime</div>
          <div className="text-xs text-[var(--color-neo-text-secondary)] mb-3">
            Clears <span className="font-mono">agent_system.db</span>, <span className="font-mono">.autocoder</span>, and
            worktrees. Keeps prompts/specs.
          </div>
          <button
            className="neo-btn neo-btn-secondary w-full text-sm"
            onClick={() => setConfirmReset(true)}
            disabled={resetProject.isPending}
          >
            <RotateCcw size={16} />
            Reset
          </button>
        </div>

        <div className="neo-card p-3">
          <div className="font-display font-bold uppercase text-sm mb-2">Full reset</div>
          <div className="text-xs text-[var(--color-neo-text-secondary)] mb-3">
            Wipes <span className="font-mono">prompts/</span> + spec status. You’ll need to recreate the spec.
          </div>
          <button
            className="neo-btn neo-btn-warning w-full text-sm"
            onClick={() => setConfirmFullReset(true)}
            disabled={resetProject.isPending}
          >
            <RotateCcw size={16} />
            Full reset
          </button>
        </div>

        <div className="neo-card p-3">
          <div className="font-display font-bold uppercase text-sm mb-2">Delete project</div>
          <label className="flex items-center gap-2 text-xs text-[var(--color-neo-text-secondary)] mb-2">
            <input
              type="checkbox"
              checked={deleteFiles}
              onChange={(e) => setDeleteFiles(e.target.checked)}
            />
            Also delete files on disk
          </label>
          <button
            className="neo-btn neo-btn-danger w-full text-sm"
            onClick={() => setConfirmDelete(true)}
            disabled={deleteProject.isPending}
          >
            <Trash2 size={16} />
            Delete
          </button>
        </div>
      </div>

      <ConfirmationDialog
        isOpen={confirmReset}
        title="Reset project runtime?"
        message={`This clears runtime state for "${projectName}" but keeps prompts/specs.`}
        confirmText="Reset"
        variant="warning"
        onCancel={() => setConfirmReset(false)}
        onConfirm={async () => {
          setConfirmReset(false)
          await handleReset(false)
        }}
      />

      <ConfirmationDialog
        isOpen={confirmFullReset}
        title="Full reset project?"
        message={`This wipes prompts/specs for "${projectName}". You will need to recreate the spec.`}
        confirmText="Full reset"
        onCancel={() => setConfirmFullReset(false)}
        onConfirm={async () => {
          setConfirmFullReset(false)
          await handleReset(true)
        }}
      />

      <ConfirmationDialog
        isOpen={confirmDelete}
        title="Delete project?"
        message={`This removes "${projectName}" from the registry${deleteFiles ? ' and deletes files on disk' : ''}.`}
        confirmText="Delete"
        onCancel={() => setConfirmDelete(false)}
        onConfirm={async () => {
          setConfirmDelete(false)
          await handleDelete()
        }}
      />
    </div>
  )
}
