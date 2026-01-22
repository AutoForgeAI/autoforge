/**
 * Schedule Modal Component
 *
 * Modal for managing agent schedules (create, edit, delete).
 * Follows neobrutalism design patterns from SettingsModal.
 */

import { useState, useEffect, useRef } from 'react'
import { Clock, GitBranch, Trash2, X } from 'lucide-react'
import {
  useSchedules,
  useCreateSchedule,
  useDeleteSchedule,
  useToggleSchedule,
} from '../hooks/useSchedules'
import {
  utcToLocalWithDayShift,
  localToUTCWithDayShift,
  adjustDaysForDayShift,
  formatDuration,
  DAYS,
  isDayActive,
  toggleDay,
} from '../lib/timeUtils'
import type { ScheduleCreate } from '../lib/types'

interface ScheduleModalProps {
  projectName: string
  isOpen: boolean
  onClose: () => void
}

export function ScheduleModal({ projectName, isOpen, onClose }: ScheduleModalProps) {
  const modalRef = useRef<HTMLDivElement>(null)
  const firstFocusableRef = useRef<HTMLButtonElement>(null)

  // Queries and mutations
  const { data: schedulesData, isLoading } = useSchedules(projectName)
  const createSchedule = useCreateSchedule(projectName)
  const deleteSchedule = useDeleteSchedule(projectName)
  const toggleSchedule = useToggleSchedule(projectName)

  // Form state for new schedule
  const [newSchedule, setNewSchedule] = useState<ScheduleCreate>({
    start_time: '22:00',
    duration_minutes: 240,
    days_of_week: 31, // Weekdays by default
    enabled: true,
    yolo_mode: false,
    model: null,
    max_concurrency: 3,
  })

  const [error, setError] = useState<string | null>(null)

  // Focus trap
  useEffect(() => {
    if (isOpen && firstFocusableRef.current) {
      firstFocusableRef.current.focus()
    }
  }, [isOpen])

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!isOpen) return

      if (e.key === 'Escape') {
        onClose()
      }

      if (e.key === 'Tab' && modalRef.current) {
        const focusableElements = modalRef.current.querySelectorAll<HTMLElement>(
          'button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
        )
        const firstElement = focusableElements[0]
        const lastElement = focusableElements[focusableElements.length - 1]

        if (e.shiftKey && document.activeElement === firstElement) {
          e.preventDefault()
          lastElement?.focus()
        } else if (!e.shiftKey && document.activeElement === lastElement) {
          e.preventDefault()
          firstElement?.focus()
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  const schedules = schedulesData?.schedules || []

  const handleCreateSchedule = async () => {
    try {
      setError(null)

      // Validate
      if (newSchedule.days_of_week === 0) {
        setError('Please select at least one day')
        return
      }

      // Validate duration
      if (newSchedule.duration_minutes < 1 || newSchedule.duration_minutes > 1440) {
        setError('Duration must be between 1 and 1440 minutes')
        return
      }

      // Convert local time to UTC and get day shift
      const { time: utcTime, dayShift } = localToUTCWithDayShift(newSchedule.start_time)

      // Adjust days_of_week based on day shift
      // If UTC is on the next day (dayShift = 1), shift days forward
      // If UTC is on the previous day (dayShift = -1), shift days backward
      const adjustedDays = adjustDaysForDayShift(newSchedule.days_of_week, dayShift)

      const scheduleToCreate = {
        ...newSchedule,
        start_time: utcTime,
        days_of_week: adjustedDays,
      }

      await createSchedule.mutateAsync(scheduleToCreate)

      // Reset form
      setNewSchedule({
        start_time: '22:00',
        duration_minutes: 240,
        days_of_week: 31,
        enabled: true,
        yolo_mode: false,
        model: null,
        max_concurrency: 3,
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create schedule')
    }
  }

  const handleToggleSchedule = async (scheduleId: number, enabled: boolean) => {
    try {
      setError(null)
      await toggleSchedule.mutateAsync({ scheduleId, enabled: !enabled })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to toggle schedule')
    }
  }

  const handleDeleteSchedule = async (scheduleId: number) => {
    if (!confirm('Are you sure you want to delete this schedule?')) return

    try {
      setError(null)
      await deleteSchedule.mutateAsync(scheduleId)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete schedule')
    }
  }

  const handleToggleDay = (dayBit: number) => {
    setNewSchedule((prev) => ({
      ...prev,
      days_of_week: toggleDay(prev.days_of_week, dayBit),
    }))
  }

  return (
    <div
      className="neo-modal-backdrop"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose()
        }
      }}
    >
      <div ref={modalRef} className="neo-modal p-6" style={{ maxWidth: '650px', maxHeight: '80vh' }}>
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-2">
            <Clock size={24} className="text-[var(--color-neo-progress)]" />
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">Agent Schedules</h2>
          </div>
          <button
            ref={firstFocusableRef}
            onClick={onClose}
            className="neo-btn neo-btn-ghost p-2"
            aria-label="Close modal"
          >
            <X size={20} />
          </button>
        </div>

        {/* Error display */}
        {error && (
          <div className="mb-4 p-3 border-2 border-red-500 bg-red-50 dark:bg-red-900/20 text-red-800 dark:text-red-200 rounded">
            {error}
          </div>
        )}

        {/* Loading state */}
        {isLoading && (
          <div className="text-center py-8 text-gray-600 dark:text-gray-300">
            Loading schedules...
          </div>
        )}

        {/* Existing schedules */}
        {!isLoading && schedules.length > 0 && (
          <div className="space-y-3 mb-6 max-h-[300px] overflow-y-auto">
            {schedules.map((schedule) => {
              // Convert UTC time to local and get day shift for display
              const { time: localTime, dayShift } = utcToLocalWithDayShift(schedule.start_time)
              const duration = formatDuration(schedule.duration_minutes)
              // Adjust displayed days: if local is next day (dayShift=1), shift forward
              // if local is prev day (dayShift=-1), shift backward
              const displayDays = adjustDaysForDayShift(schedule.days_of_week, dayShift)

              return (
                <div
                  key={schedule.id}
                  className="neo-card p-4 flex items-start justify-between gap-4"
                >
                  <div className="flex-1">
                    {/* Time and duration */}
                    <div className="flex items-baseline gap-2 mb-2">
                      <span className="text-lg font-bold text-gray-900 dark:text-white">{localTime}</span>
                      <span className="text-sm text-gray-600 dark:text-gray-300">
                        for {duration}
                      </span>
                    </div>

                    {/* Days */}
                    <div className="flex gap-1 mb-2">
                      {DAYS.map((day) => {
                        const isActive = isDayActive(displayDays, day.bit)
                        return (
                          <span
                            key={day.label}
                            className={`text-xs px-2 py-1 rounded border-2 ${
                              isActive
                                ? 'border-[var(--color-neo-progress)] bg-[var(--color-neo-progress)] text-white font-bold'
                                : 'border-gray-300 dark:border-gray-600 text-gray-400 dark:text-gray-500'
                            }`}
                          >
                            {day.label}
                          </span>
                        )
                      })}
                    </div>

                    {/* Metadata */}
                    <div className="flex gap-3 text-xs text-gray-600 dark:text-gray-300">
                      {schedule.yolo_mode && (
                        <span className="font-bold text-yellow-600">⚡ YOLO mode</span>
                      )}
                      <span className="flex items-center gap-1">
                        <GitBranch size={12} />
                        {schedule.max_concurrency}x
                      </span>
                      {schedule.model && <span>Model: {schedule.model}</span>}
                      {schedule.crash_count > 0 && (
                        <span className="text-red-600">Crashes: {schedule.crash_count}</span>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="flex items-center gap-2">
                    {/* Enable/disable toggle */}
                    <button
                      onClick={() => handleToggleSchedule(schedule.id, schedule.enabled)}
                      className={`neo-btn neo-btn-ghost px-3 py-1 text-xs font-bold ${
                        schedule.enabled
                          ? 'text-[var(--color-neo-done)]'
                          : 'text-[var(--color-neo-text-secondary)]'
                      }`}
                      disabled={toggleSchedule.isPending}
                    >
                      {schedule.enabled ? 'Enabled' : 'Disabled'}
                    </button>

                    {/* Delete button */}
                    <button
                      onClick={() => handleDeleteSchedule(schedule.id)}
                      className="neo-btn neo-btn-ghost p-2 text-red-600 hover:bg-red-50"
                      disabled={deleteSchedule.isPending}
                      aria-label="Delete schedule"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Empty state */}
        {!isLoading && schedules.length === 0 && (
          <div className="text-center py-6 text-gray-600 dark:text-gray-300 mb-6">
            <Clock size={48} className="mx-auto mb-2 opacity-50 text-gray-400 dark:text-gray-500" />
            <p>No schedules configured yet</p>
          </div>
        )}

        {/* Divider */}
        <div className="border-t-2 border-gray-200 dark:border-gray-700 my-6"></div>

        {/* Add new schedule form */}
        <div>
          <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4">Add New Schedule</h3>

          {/* Time and duration */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-sm font-bold text-gray-700 dark:text-gray-200 mb-2">Start Time (Local)</label>
              <input
                type="time"
                value={newSchedule.start_time}
                onChange={(e) =>
                  setNewSchedule((prev) => ({ ...prev, start_time: e.target.value }))
                }
                className="neo-input w-full"
              />
            </div>
            <div>
              <label className="block text-sm font-bold text-gray-700 dark:text-gray-200 mb-2">Duration (minutes)</label>
              <input
                type="number"
                min="1"
                max="1440"
                value={newSchedule.duration_minutes}
                onChange={(e) => {
                  const parsed = parseInt(e.target.value, 10)
                  const value = isNaN(parsed) ? 1 : Math.max(1, Math.min(1440, parsed))
                  setNewSchedule((prev) => ({
                    ...prev,
                    duration_minutes: value,
                  }))
                }}
                className="neo-input w-full"
              />
              <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">
                {formatDuration(newSchedule.duration_minutes)}
              </div>
            </div>
          </div>

          {/* Days of week */}
          <div className="mb-4">
            <label className="block text-sm font-bold text-gray-700 dark:text-gray-200 mb-2">Days</label>
            <div className="flex gap-2">
              {DAYS.map((day) => {
                const isActive = isDayActive(newSchedule.days_of_week, day.bit)
                return (
                  <button
                    key={day.label}
                    onClick={() => handleToggleDay(day.bit)}
                    className={`neo-btn px-3 py-2 text-sm ${
                      isActive
                        ? 'bg-[var(--color-neo-progress)] text-white border-[var(--color-neo-progress)]'
                        : 'neo-btn-ghost'
                    }`}
                  >
                    {day.label}
                  </button>
                )
              })}
            </div>
          </div>

          {/* YOLO mode toggle */}
          <div className="mb-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={newSchedule.yolo_mode}
                onChange={(e) =>
                  setNewSchedule((prev) => ({ ...prev, yolo_mode: e.target.checked }))
                }
                className="w-4 h-4"
              />
              <span className="text-sm font-bold text-gray-700 dark:text-gray-200">YOLO Mode (skip testing)</span>
            </label>
          </div>

          {/* Concurrency slider */}
          <div className="mb-4">
            <label className="block text-sm font-bold text-gray-700 dark:text-gray-200 mb-2">
              Concurrent Agents (1-5)
            </label>
            <div className="flex items-center gap-3">
              <GitBranch
                size={16}
                className={newSchedule.max_concurrency > 1 ? 'text-[var(--color-neo-primary)]' : 'text-gray-400'}
              />
              <input
                type="range"
                min={1}
                max={5}
                value={newSchedule.max_concurrency}
                onChange={(e) =>
                  setNewSchedule((prev) => ({ ...prev, max_concurrency: Number(e.target.value) }))
                }
                className="flex-1 h-2 accent-[var(--color-neo-primary)] cursor-pointer"
                title={`${newSchedule.max_concurrency} concurrent agent${newSchedule.max_concurrency > 1 ? 's' : ''}`}
                aria-label="Set number of concurrent agents"
              />
              <span className="text-sm font-bold min-w-[2rem] text-center text-gray-900 dark:text-white">
                {newSchedule.max_concurrency}x
              </span>
            </div>
            <div className="text-xs text-gray-600 dark:text-gray-400 mt-1">
              Run {newSchedule.max_concurrency} agent{newSchedule.max_concurrency > 1 ? 's' : ''} in parallel for faster feature completion
            </div>
          </div>

          {/* Model selection (optional) */}
          <div className="mb-6">
            <label className="block text-sm font-bold text-gray-700 dark:text-gray-200 mb-2">
              Model (optional, defaults to global setting)
            </label>
            <input
              type="text"
              placeholder="e.g., claude-3-5-sonnet-20241022"
              value={newSchedule.model || ''}
              onChange={(e) =>
                setNewSchedule((prev) => ({ ...prev, model: e.target.value || null }))
              }
              className="neo-input w-full"
            />
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3">
            <button onClick={onClose} className="neo-btn neo-btn-ghost">
              Close
            </button>
            <button
              onClick={handleCreateSchedule}
              disabled={createSchedule.isPending || newSchedule.days_of_week === 0}
              className="neo-btn neo-btn-primary"
            >
              {createSchedule.isPending ? 'Creating...' : 'Create Schedule'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
