import { useState } from 'react'
import { X, CheckCircle2, XCircle, BarChart3, Star, AlertTriangle } from 'lucide-react'
import type { PhaseData } from './PhaseCard'

interface PhaseStatistics {
  total_tasks: number
  passing_tasks: number
  reviewed_tasks: number
  blocked_tasks: number
  average_review_score: number | null
  review_coverage: number
}

interface PhaseApprovalModalProps {
  phase: PhaseData
  statistics?: PhaseStatistics
  onApprove: (notes?: string) => void
  onReject: (notes: string) => void
  onClose: () => void
  isLoading?: boolean
}

export function PhaseApprovalModal({
  phase,
  statistics,
  onApprove,
  onReject,
  onClose,
  isLoading = false,
}: PhaseApprovalModalProps) {
  const [mode, setMode] = useState<'review' | 'approve' | 'reject'>('review')
  const [notes, setNotes] = useState('')

  const handleApprove = () => {
    onApprove(notes || undefined)
  }

  const handleReject = () => {
    if (!notes.trim()) {
      return // Rejection requires notes
    }
    onReject(notes)
  }

  // Quality warnings
  const warnings: string[] = []
  if (statistics) {
    if (statistics.review_coverage < 50) {
      warnings.push(`Low review coverage: only ${statistics.review_coverage}% of tasks reviewed`)
    }
    if (statistics.average_review_score && statistics.average_review_score < 3) {
      warnings.push(`Low average review score: ${statistics.average_review_score}/5`)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="neo-card max-w-lg w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--color-neo-border)]">
          <h2 className="font-display font-bold text-lg">Phase Approval</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-[var(--color-neo-bg)] rounded"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="p-4 space-y-4">
          {/* Phase Info */}
          <div className="neo-card bg-[var(--color-neo-bg)] p-4">
            <div className="text-xs text-[var(--color-neo-text-secondary)] font-mono mb-1">
              Phase {phase.order + 1}
            </div>
            <h3 className="font-bold text-lg">{phase.name}</h3>
          </div>

          {/* Statistics */}
          {statistics && (
            <div className="grid grid-cols-2 gap-3">
              <div className="neo-card p-3 text-center">
                <div className="flex items-center justify-center gap-1 text-[var(--color-neo-done)]">
                  <BarChart3 size={16} />
                  <span className="font-bold text-lg">{statistics.passing_tasks}</span>
                </div>
                <div className="text-xs text-[var(--color-neo-text-secondary)]">
                  Tasks Complete
                </div>
              </div>
              <div className="neo-card p-3 text-center">
                <div className="flex items-center justify-center gap-1 text-blue-500">
                  <CheckCircle2 size={16} />
                  <span className="font-bold text-lg">{statistics.reviewed_tasks}</span>
                </div>
                <div className="text-xs text-[var(--color-neo-text-secondary)]">
                  Tasks Reviewed
                </div>
              </div>
              <div className="neo-card p-3 text-center">
                <div className="flex items-center justify-center gap-1 text-purple-500">
                  <Star size={16} />
                  <span className="font-bold text-lg">
                    {statistics.average_review_score?.toFixed(1) || 'N/A'}
                  </span>
                </div>
                <div className="text-xs text-[var(--color-neo-text-secondary)]">
                  Avg Review Score
                </div>
              </div>
              <div className="neo-card p-3 text-center">
                <div className="font-bold text-lg text-[var(--color-neo-progress)]">
                  {statistics.review_coverage}%
                </div>
                <div className="text-xs text-[var(--color-neo-text-secondary)]">
                  Review Coverage
                </div>
              </div>
            </div>
          )}

          {/* Warnings */}
          {warnings.length > 0 && (
            <div className="neo-card bg-amber-50 border-amber-500 p-3">
              <div className="flex items-center gap-2 text-amber-700 font-bold mb-2">
                <AlertTriangle size={16} />
                Quality Warnings
              </div>
              <ul className="text-sm text-amber-700 space-y-1">
                {warnings.map((warning, i) => (
                  <li key={i}>• {warning}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Action Selection */}
          {mode === 'review' && (
            <div className="flex gap-3">
              <button
                onClick={() => setMode('approve')}
                className="neo-button flex-1 flex items-center justify-center gap-2 bg-green-500 text-white hover:bg-green-600"
              >
                <CheckCircle2 size={18} />
                Approve Phase
              </button>
              <button
                onClick={() => setMode('reject')}
                className="neo-button flex-1 flex items-center justify-center gap-2 bg-red-500 text-white hover:bg-red-600"
              >
                <XCircle size={18} />
                Reject Phase
              </button>
            </div>
          )}

          {/* Approve Form */}
          {mode === 'approve' && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-green-600 font-bold">
                <CheckCircle2 size={20} />
                Approve Phase
              </div>
              <p className="text-sm text-[var(--color-neo-text-secondary)]">
                Approving will mark this phase as complete and automatically start the next phase.
              </p>
              <div>
                <label className="block text-sm font-bold mb-1">
                  Approval Notes (optional)
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="neo-input w-full h-24 resize-none"
                  placeholder="Add any notes about this approval..."
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setMode('review')}
                  className="neo-button flex-1"
                  disabled={isLoading}
                >
                  Back
                </button>
                <button
                  onClick={handleApprove}
                  className="neo-button flex-1 bg-green-500 text-white hover:bg-green-600"
                  disabled={isLoading}
                >
                  {isLoading ? 'Approving...' : 'Confirm Approval'}
                </button>
              </div>
            </div>
          )}

          {/* Reject Form */}
          {mode === 'reject' && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-red-600 font-bold">
                <XCircle size={20} />
                Reject Phase
              </div>
              <p className="text-sm text-[var(--color-neo-text-secondary)]">
                Rejecting will return this phase to "in progress" status. Please provide detailed feedback.
              </p>
              <div>
                <label className="block text-sm font-bold mb-1">
                  Rejection Notes (required)
                </label>
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  className="neo-input w-full h-24 resize-none"
                  placeholder="Explain what needs to be fixed before approval..."
                  required
                />
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setMode('review')}
                  className="neo-button flex-1"
                  disabled={isLoading}
                >
                  Back
                </button>
                <button
                  onClick={handleReject}
                  className="neo-button flex-1 bg-red-500 text-white hover:bg-red-600"
                  disabled={isLoading || !notes.trim()}
                >
                  {isLoading ? 'Rejecting...' : 'Confirm Rejection'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
