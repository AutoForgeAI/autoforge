import { useState } from 'react'
import {
  X,
  Plus,
  Trash2,
  Sparkles,
  ListTodo,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  Loader2,
} from 'lucide-react'

interface TaskInput {
  id: string
  name: string
  description: string
  priority: number
  estimated_complexity: number
  steps: string[]
}

interface AddFeatureModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (feature: {
    name: string
    description: string
    phaseId?: number
    tasks: Omit<TaskInput, 'id'>[]
  }) => Promise<void>
  phases?: { id: number; name: string }[]
  onGenerateTasks?: (featureDescription: string) => Promise<TaskInput[]>
  projectName: string
}

function generateId(): string {
  return Math.random().toString(36).substring(2, 9)
}

function TaskInputRow({
  task,
  index,
  onUpdate,
  onRemove,
  isExpanded,
  onToggleExpand,
}: {
  task: TaskInput
  index: number
  onUpdate: (task: TaskInput) => void
  onRemove: () => void
  isExpanded: boolean
  onToggleExpand: () => void
}) {
  const addStep = () => {
    onUpdate({
      ...task,
      steps: [...task.steps, ''],
    })
  }

  const updateStep = (stepIndex: number, value: string) => {
    const newSteps = [...task.steps]
    newSteps[stepIndex] = value
    onUpdate({ ...task, steps: newSteps })
  }

  const removeStep = (stepIndex: number) => {
    onUpdate({
      ...task,
      steps: task.steps.filter((_, i) => i !== stepIndex),
    })
  }

  return (
    <div className="neo-card p-3 bg-[var(--color-neo-bg)]">
      <div className="flex items-start gap-3">
        <span className="w-6 h-6 rounded-full bg-[var(--color-neo-accent)] text-white flex items-center justify-center text-sm font-bold">
          {index + 1}
        </span>

        <div className="flex-1 space-y-2">
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={task.name}
              onChange={(e) => onUpdate({ ...task, name: e.target.value })}
              placeholder="Task name"
              className="neo-input flex-1 text-sm"
            />
            <button
              onClick={onToggleExpand}
              className="neo-button p-2"
              title={isExpanded ? 'Collapse' : 'Expand'}
            >
              {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
            </button>
            <button
              onClick={onRemove}
              className="neo-button p-2 text-red-500 hover:bg-red-100"
              title="Remove task"
            >
              <Trash2 size={14} />
            </button>
          </div>

          {isExpanded && (
            <>
              <textarea
                value={task.description}
                onChange={(e) => onUpdate({ ...task, description: e.target.value })}
                placeholder="Task description"
                className="neo-input w-full text-sm"
                rows={2}
              />

              <div className="flex gap-4">
                <div className="flex-1">
                  <label className="block text-xs text-[var(--color-neo-text-secondary)] mb-1">
                    Priority (1-1000)
                  </label>
                  <input
                    type="number"
                    value={task.priority}
                    onChange={(e) => onUpdate({ ...task, priority: parseInt(e.target.value) || 1 })}
                    min={1}
                    max={1000}
                    className="neo-input w-full text-sm"
                  />
                </div>
                <div className="flex-1">
                  <label className="block text-xs text-[var(--color-neo-text-secondary)] mb-1">
                    Complexity (1-5)
                  </label>
                  <select
                    value={task.estimated_complexity}
                    onChange={(e) => onUpdate({ ...task, estimated_complexity: parseInt(e.target.value) })}
                    className="neo-input w-full text-sm"
                  >
                    <option value={1}>1 - Simple</option>
                    <option value={2}>2 - Easy</option>
                    <option value={3}>3 - Moderate</option>
                    <option value={4}>4 - Complex</option>
                    <option value={5}>5 - Very Complex</option>
                  </select>
                </div>
              </div>

              {/* Steps */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs text-[var(--color-neo-text-secondary)]">
                    Implementation Steps
                  </label>
                  <button
                    onClick={addStep}
                    className="neo-button p-1 text-xs flex items-center gap-1"
                  >
                    <Plus size={12} />
                    Add Step
                  </button>
                </div>
                <div className="space-y-1">
                  {task.steps.map((step, stepIndex) => (
                    <div key={stepIndex} className="flex items-center gap-2">
                      <span className="text-xs text-[var(--color-neo-text-secondary)] w-4">
                        {stepIndex + 1}.
                      </span>
                      <input
                        type="text"
                        value={step}
                        onChange={(e) => updateStep(stepIndex, e.target.value)}
                        placeholder={`Step ${stepIndex + 1}`}
                        className="neo-input flex-1 text-xs"
                      />
                      <button
                        onClick={() => removeStep(stepIndex)}
                        className="text-red-500 hover:text-red-700 p-1"
                        title="Remove step"
                      >
                        <X size={12} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export function AddFeatureModal({
  isOpen,
  onClose,
  onSubmit,
  phases = [],
  onGenerateTasks,
  projectName,
}: AddFeatureModalProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [selectedPhaseId, setSelectedPhaseId] = useState<number | undefined>()
  const [tasks, setTasks] = useState<TaskInput[]>([])
  const [expandedTasks, setExpandedTasks] = useState<Set<string>>(new Set())
  const [isGenerating, setIsGenerating] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isOpen) return null

  const handleAddTask = () => {
    const newTask: TaskInput = {
      id: generateId(),
      name: '',
      description: '',
      priority: (tasks.length + 1) * 10,
      estimated_complexity: 2,
      steps: [''],
    }
    setTasks([...tasks, newTask])
    setExpandedTasks(new Set([...expandedTasks, newTask.id]))
  }

  const handleUpdateTask = (taskId: string, updatedTask: TaskInput) => {
    setTasks(tasks.map(t => t.id === taskId ? updatedTask : t))
  }

  const handleRemoveTask = (taskId: string) => {
    setTasks(tasks.filter(t => t.id !== taskId))
    expandedTasks.delete(taskId)
    setExpandedTasks(new Set(expandedTasks))
  }

  const toggleTaskExpand = (taskId: string) => {
    const newExpanded = new Set(expandedTasks)
    if (newExpanded.has(taskId)) {
      newExpanded.delete(taskId)
    } else {
      newExpanded.add(taskId)
    }
    setExpandedTasks(newExpanded)
  }

  const handleGenerateTasks = async () => {
    if (!description.trim() || !onGenerateTasks) return

    setIsGenerating(true)
    setError(null)

    try {
      const generatedTasks = await onGenerateTasks(description)
      setTasks(generatedTasks)
      // Expand all generated tasks
      setExpandedTasks(new Set(generatedTasks.map(t => t.id)))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate tasks')
    } finally {
      setIsGenerating(false)
    }
  }

  const handleSubmit = async () => {
    if (!name.trim()) {
      setError('Feature name is required')
      return
    }

    if (tasks.length === 0) {
      setError('At least one task is required')
      return
    }

    // Validate tasks
    for (const task of tasks) {
      if (!task.name.trim()) {
        setError('All tasks must have a name')
        return
      }
    }

    setIsSubmitting(true)
    setError(null)

    try {
      await onSubmit({
        name: name.trim(),
        description: description.trim(),
        phaseId: selectedPhaseId,
        tasks: tasks.map(({ id: _id, ...rest }) => rest),
      })

      // Reset form
      setName('')
      setDescription('')
      setSelectedPhaseId(undefined)
      setTasks([])
      setExpandedTasks(new Set())
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create feature')
    } finally {
      setIsSubmitting(false)
    }
  }

  const handleClose = () => {
    if (!isSubmitting && !isGenerating) {
      onClose()
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={handleClose}
      />

      {/* Modal */}
      <div className="relative neo-card w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col m-4">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--color-neo-border)]">
          <h2 className="font-display font-bold text-xl flex items-center gap-2">
            <ListTodo size={24} />
            Add Feature
          </h2>
          <button
            onClick={handleClose}
            disabled={isSubmitting || isGenerating}
            className="neo-button p-2"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4 space-y-4">
          {/* Error message */}
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-100 border border-red-300 rounded-lg text-red-700 text-sm">
              <AlertCircle size={16} />
              {error}
            </div>
          )}

          {/* Feature info */}
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-bold mb-1">
                Feature Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., User Authentication"
                className="neo-input w-full"
                disabled={isSubmitting}
              />
            </div>

            <div>
              <label className="block text-sm font-bold mb-1">
                Description
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what this feature should accomplish..."
                className="neo-input w-full"
                rows={3}
                disabled={isSubmitting}
              />
            </div>

            {phases.length > 0 && (
              <div>
                <label className="block text-sm font-bold mb-1">
                  Phase (Optional)
                </label>
                <select
                  value={selectedPhaseId ?? ''}
                  onChange={(e) => setSelectedPhaseId(e.target.value ? parseInt(e.target.value) : undefined)}
                  className="neo-input w-full"
                  disabled={isSubmitting}
                >
                  <option value="">No phase</option>
                  {phases.map(phase => (
                    <option key={phase.id} value={phase.id}>
                      {phase.name}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>

          {/* Tasks section */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="font-bold text-sm">
                Tasks <span className="text-red-500">*</span>
                <span className="text-[var(--color-neo-text-secondary)] font-normal ml-2">
                  ({tasks.length} {tasks.length === 1 ? 'task' : 'tasks'})
                </span>
              </h3>
              <div className="flex gap-2">
                {onGenerateTasks && (
                  <button
                    onClick={handleGenerateTasks}
                    disabled={!description.trim() || isGenerating || isSubmitting}
                    className="neo-button flex items-center gap-1 text-sm bg-purple-500 text-white disabled:opacity-50"
                  >
                    {isGenerating ? (
                      <Loader2 size={14} className="animate-spin" />
                    ) : (
                      <Sparkles size={14} />
                    )}
                    {isGenerating ? 'Generating...' : 'Generate Tasks'}
                  </button>
                )}
                <button
                  onClick={handleAddTask}
                  disabled={isSubmitting}
                  className="neo-button flex items-center gap-1 text-sm"
                >
                  <Plus size={14} />
                  Add Task
                </button>
              </div>
            </div>

            {tasks.length === 0 ? (
              <div className="text-center py-8 text-[var(--color-neo-text-secondary)]">
                <ListTodo size={32} className="mx-auto mb-2 opacity-50" />
                <p>No tasks yet</p>
                <p className="text-xs mt-1">
                  Add tasks manually or generate them from the description
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {tasks.map((task, index) => (
                  <TaskInputRow
                    key={task.id}
                    task={task}
                    index={index}
                    onUpdate={(updated) => handleUpdateTask(task.id, updated)}
                    onRemove={() => handleRemoveTask(task.id)}
                    isExpanded={expandedTasks.has(task.id)}
                    onToggleExpand={() => toggleTaskExpand(task.id)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-[var(--color-neo-border)] bg-[var(--color-neo-bg)]">
          <div className="text-sm text-[var(--color-neo-text-secondary)]">
            Adding to: <span className="font-bold">{projectName}</span>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleClose}
              disabled={isSubmitting || isGenerating}
              className="neo-button"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              disabled={isSubmitting || isGenerating || !name.trim() || tasks.length === 0}
              className="neo-button bg-[var(--color-neo-accent)] text-white disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={16} className="animate-spin mr-2" />
                  Creating...
                </>
              ) : (
                <>
                  <Plus size={16} className="mr-2" />
                  Create Feature
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
