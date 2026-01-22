/**
 * Conversation History Dropdown Component
 *
 * Displays a list of past conversations for the assistant.
 * Allows selecting a conversation to resume or deleting old conversations.
 */

import { useState, useEffect } from 'react'
import { MessageSquare, Trash2, Loader2, AlertCircle } from 'lucide-react'
import { useConversations, useDeleteConversation } from '../hooks/useConversations'
import { ConfirmDialog } from './ConfirmDialog'
import type { AssistantConversation } from '../lib/types'

interface ConversationHistoryProps {
  projectName: string
  currentConversationId: number | null
  isOpen: boolean
  onClose: () => void
  onSelectConversation: (conversationId: number) => void
}

/**
 * Format a relative time string from an ISO date
 */
function formatRelativeTime(dateString: string | null): string {
  if (!dateString) return ''

  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSeconds = Math.floor(diffMs / 1000)
  const diffMinutes = Math.floor(diffSeconds / 60)
  const diffHours = Math.floor(diffMinutes / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSeconds < 60) return 'just now'
  if (diffMinutes < 60) return `${diffMinutes}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays === 1) return 'yesterday'
  if (diffDays < 7) return `${diffDays}d ago`

  return date.toLocaleDateString()
}

export function ConversationHistory({
  projectName,
  currentConversationId,
  isOpen,
  onClose,
  onSelectConversation,
}: ConversationHistoryProps) {
  const [conversationToDelete, setConversationToDelete] = useState<AssistantConversation | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const { data: conversations, isLoading } = useConversations(projectName)
  const deleteConversation = useDeleteConversation(projectName)

  // Clear error when dropdown closes
  useEffect(() => {
    if (!isOpen) {
      setDeleteError(null)
    }
  }, [isOpen])

  const handleDeleteClick = (e: React.MouseEvent, conversation: AssistantConversation) => {
    e.stopPropagation()
    setConversationToDelete(conversation)
  }

  const handleConfirmDelete = async () => {
    if (!conversationToDelete) return

    try {
      setDeleteError(null)
      await deleteConversation.mutateAsync(conversationToDelete.id)
      setConversationToDelete(null)
    } catch {
      // Keep dialog open and show error to user
      setDeleteError('Failed to delete conversation. Please try again.')
    }
  }

  const handleCancelDelete = () => {
    setConversationToDelete(null)
    setDeleteError(null)
  }

  const handleSelectConversation = (conversationId: number) => {
    onSelectConversation(conversationId)
    onClose()
  }

  // Handle Escape key to close dropdown
  useEffect(() => {
    if (!isOpen) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        onClose()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40"
        onClick={onClose}
      />

      {/* Dropdown */}
      <div
        className="absolute top-full left-0 mt-2 neo-dropdown z-50 w-[320px] max-w-[calc(100vw-2rem)]"
        style={{ boxShadow: 'var(--shadow-neo)' }}
      >
        {/* Header */}
        <div className="px-3 py-2 border-b-2 border-[var(--color-neo-border)] bg-[var(--color-neo-bg)]">
          <h3 className="font-bold text-sm">Conversation History</h3>
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="p-4 flex items-center justify-center">
            <Loader2 size={20} className="animate-spin text-[var(--color-neo-text-secondary)]" />
          </div>
        ) : !conversations || conversations.length === 0 ? (
          <div className="p-4 text-center text-[var(--color-neo-text-secondary)] text-sm">
            No conversations yet
          </div>
        ) : (
          <div className="max-h-[300px] overflow-auto">
            {conversations.map((conversation) => {
              const isCurrent = conversation.id === currentConversationId

              return (
                <div
                  key={conversation.id}
                  className={`flex items-center group ${
                    isCurrent
                      ? 'bg-[var(--color-neo-pending)] text-[var(--color-neo-text-on-bright)]'
                      : ''
                  }`}
                >
                  <button
                    onClick={() => handleSelectConversation(conversation.id)}
                    className="flex-1 neo-dropdown-item text-left"
                    disabled={isCurrent}
                  >
                    <div className="flex items-start gap-2">
                      <MessageSquare size={16} className="mt-0.5 flex-shrink-0" />
                      <div className="flex-1 min-w-0">
                        <div className="font-medium truncate">
                          {conversation.title || 'Untitled conversation'}
                        </div>
                        <div className={`text-xs flex items-center gap-2 ${
                          isCurrent
                            ? 'text-[var(--color-neo-text-on-bright)] opacity-80'
                            : 'text-[var(--color-neo-text-secondary)]'
                        }`}>
                          <span>{conversation.message_count} messages</span>
                          <span>|</span>
                          <span>{formatRelativeTime(conversation.updated_at)}</span>
                        </div>
                      </div>
                    </div>
                  </button>
                  <button
                    onClick={(e) => handleDeleteClick(e, conversation)}
                    className={`p-2 mr-2 transition-colors rounded ${
                      isCurrent
                        ? 'text-[var(--color-neo-text-on-bright)] opacity-60 hover:opacity-100 hover:bg-[var(--color-neo-danger)]/20'
                        : 'text-[var(--color-neo-text-secondary)] opacity-0 group-hover:opacity-100 hover:text-[var(--color-neo-danger)] hover:bg-[var(--color-neo-danger)]/10'
                    }`}
                    title="Delete conversation"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        isOpen={conversationToDelete !== null}
        title="Delete Conversation"
        message={
          deleteError ? (
            <div className="space-y-3">
              <p>{`Are you sure you want to delete "${conversationToDelete?.title || 'this conversation'}"? This action cannot be undone.`}</p>
              <div className="flex items-center gap-2 p-2 bg-[var(--color-neo-danger)]/10 border border-[var(--color-neo-danger)] rounded text-sm text-[var(--color-neo-danger)]">
                <AlertCircle size={16} className="flex-shrink-0" />
                <span>{deleteError}</span>
              </div>
            </div>
          ) : (
            `Are you sure you want to delete "${conversationToDelete?.title || 'this conversation'}"? This action cannot be undone.`
          )
        }
        confirmLabel="Delete"
        cancelLabel="Cancel"
        variant="danger"
        isLoading={deleteConversation.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={handleCancelDelete}
      />
    </>
  )
}
