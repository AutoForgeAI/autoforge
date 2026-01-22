/**
 * Assistant Chat Component
 *
 * Main chat interface for the project assistant.
 * Displays messages and handles user input.
 * Supports conversation history with resume functionality.
 */

import { useState, useRef, useEffect, useCallback, useMemo } from 'react'
import { Send, Loader2, Wifi, WifiOff, Plus, History } from 'lucide-react'
import { useAssistantChat } from '../hooks/useAssistantChat'
import { ChatMessage as ChatMessageComponent } from './ChatMessage'
import { ConversationHistory } from './ConversationHistory'
import type { ChatMessage } from '../lib/types'

interface AssistantChatProps {
  projectName: string
  conversationId?: number | null
  initialMessages?: ChatMessage[]
  isLoadingConversation?: boolean
  onNewChat?: () => void
  onSelectConversation?: (id: number) => void
  onConversationCreated?: (id: number) => void
}

export function AssistantChat({
  projectName,
  conversationId,
  initialMessages,
  isLoadingConversation,
  onNewChat,
  onSelectConversation,
  onConversationCreated,
}: AssistantChatProps) {
  const [inputValue, setInputValue] = useState('')
  const [showHistory, setShowHistory] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const hasStartedRef = useRef(false)
  const lastConversationIdRef = useRef<number | null | undefined>(undefined)

  // Memoize the error handler to prevent infinite re-renders
  const handleError = useCallback((error: string) => {
    console.error('Assistant error:', error)
  }, [])

  const {
    messages,
    isLoading,
    connectionStatus,
    conversationId: activeConversationId,
    start,
    sendMessage,
    clearMessages,
  } = useAssistantChat({
    projectName,
    onError: handleError,
  })

  // Notify parent when a NEW conversation is created (not when switching to existing)
  // Track activeConversationId to fire callback only once when it transitions from null to a value
  const previousActiveConversationIdRef = useRef<number | null>(activeConversationId)
  useEffect(() => {
    const hadNoConversation = previousActiveConversationIdRef.current === null
    const nowHasConversation = activeConversationId !== null

    if (hadNoConversation && nowHasConversation && onConversationCreated) {
      onConversationCreated(activeConversationId)
    }

    previousActiveConversationIdRef.current = activeConversationId
  }, [activeConversationId, onConversationCreated])

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Start or resume the chat session when component mounts or conversationId changes
  useEffect(() => {
    // Skip if we're loading conversation details
    if (isLoadingConversation) {
      return
    }

    // Only start if conversationId has actually changed
    if (lastConversationIdRef.current === conversationId && hasStartedRef.current) {
      return
    }

    // Check if we're switching to a different conversation (not initial mount)
    const isSwitching = lastConversationIdRef.current !== undefined &&
                        lastConversationIdRef.current !== conversationId

    lastConversationIdRef.current = conversationId
    hasStartedRef.current = true

    // Clear existing messages when switching conversations
    if (isSwitching) {
      clearMessages()
    }

    // Start the session with the conversation ID (or null for new)
    start(conversationId)
  }, [conversationId, isLoadingConversation, start, clearMessages])

  // Handle starting a new chat
  const handleNewChat = useCallback(() => {
    clearMessages()
    onNewChat?.()
  }, [clearMessages, onNewChat])

  // Handle selecting a conversation from history
  const handleSelectConversation = useCallback((id: number) => {
    setShowHistory(false)
    onSelectConversation?.(id)
  }, [onSelectConversation])

  // Focus input when not loading
  useEffect(() => {
    if (!isLoading) {
      inputRef.current?.focus()
    }
  }, [isLoading])

  const handleSend = () => {
    const content = inputValue.trim()
    if (!content || isLoading || isLoadingConversation) return

    sendMessage(content)
    setInputValue('')
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // Combine initial messages (from resumed conversation) with live messages
  // Merge both arrays with deduplication by message ID to prevent history loss
  const displayMessages = useMemo(() => {
    const isConversationSynced = lastConversationIdRef.current === conversationId && !isLoadingConversation

    // If not synced yet, show only initialMessages (or empty)
    if (!isConversationSynced) {
      return initialMessages ?? []
    }

    // If no initial messages, just show live messages
    if (!initialMessages || initialMessages.length === 0) {
      return messages
    }

    // Merge both arrays, deduplicating by ID (live messages take precedence)
    const messageMap = new Map<string, ChatMessage>()
    for (const msg of initialMessages) {
      messageMap.set(msg.id, msg)
    }
    for (const msg of messages) {
      messageMap.set(msg.id, msg)
    }
    return Array.from(messageMap.values())
  }, [initialMessages, messages, conversationId, isLoadingConversation])

  return (
    <div className="flex flex-col h-full">
      {/* Header with actions and connection status */}
      <div className="flex items-center justify-between px-4 py-2 border-b-2 border-[var(--color-neo-border)] bg-[var(--color-neo-bg)]">
        {/* Action buttons */}
        <div className="flex items-center gap-1 relative">
          <button
            onClick={handleNewChat}
            className="neo-btn neo-btn-ghost p-1.5 text-[var(--color-neo-text-secondary)] hover:text-[var(--color-neo-text)]"
            title="New conversation"
            disabled={isLoading}
          >
            <Plus size={16} />
          </button>
          <button
            onClick={() => setShowHistory(!showHistory)}
            className={`neo-btn neo-btn-ghost p-1.5 ${
              showHistory
                ? 'text-[var(--color-neo-text)] bg-[var(--color-neo-pending)]'
                : 'text-[var(--color-neo-text-secondary)] hover:text-[var(--color-neo-text)]'
            }`}
            title="Conversation history"
          >
            <History size={16} />
          </button>

          {/* History dropdown */}
          <ConversationHistory
            projectName={projectName}
            currentConversationId={conversationId ?? activeConversationId}
            isOpen={showHistory}
            onClose={() => setShowHistory(false)}
            onSelectConversation={handleSelectConversation}
          />
        </div>

        {/* Connection status */}
        <div className="flex items-center gap-2">
          {connectionStatus === 'connected' ? (
            <>
              <Wifi size={14} className="text-[var(--color-neo-done)]" />
              <span className="text-xs text-[var(--color-neo-text-secondary)]">Connected</span>
            </>
          ) : connectionStatus === 'connecting' ? (
            <>
              <Loader2 size={14} className="text-[var(--color-neo-progress)] animate-spin" />
              <span className="text-xs text-[var(--color-neo-text-secondary)]">Connecting...</span>
            </>
          ) : (
            <>
              <WifiOff size={14} className="text-[var(--color-neo-danger)]" />
              <span className="text-xs text-[var(--color-neo-text-secondary)]">Disconnected</span>
            </>
          )}
        </div>
      </div>

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto bg-[var(--color-neo-bg)]">
        {isLoadingConversation ? (
          <div className="flex items-center justify-center h-full text-[var(--color-neo-text-secondary)] text-sm">
            <div className="flex items-center gap-2">
              <Loader2 size={16} className="animate-spin" />
              <span>Loading conversation...</span>
            </div>
          </div>
        ) : displayMessages.length === 0 ? (
          <div className="flex items-center justify-center h-full text-[var(--color-neo-text-secondary)] text-sm">
            {isLoading ? (
              <div className="flex items-center gap-2">
                <Loader2 size={16} className="animate-spin" />
                <span>Connecting to assistant...</span>
              </div>
            ) : (
              <span>Ask me anything about the codebase</span>
            )}
          </div>
        ) : (
          <div className="py-4">
            {displayMessages.map((message) => (
              <ChatMessageComponent key={message.id} message={message} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Loading indicator */}
      {isLoading && displayMessages.length > 0 && (
        <div className="px-4 py-2 border-t-2 border-[var(--color-neo-border)] bg-[var(--color-neo-bg)]">
          <div className="flex items-center gap-2 text-[var(--color-neo-text-secondary)] text-sm">
            <div className="flex gap-1">
              <span className="w-2 h-2 bg-[var(--color-neo-progress)] rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 bg-[var(--color-neo-progress)] rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 bg-[var(--color-neo-progress)] rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
            <span>Thinking...</span>
          </div>
        </div>
      )}

      {/* Input area */}
      <div className="border-t-3 border-[var(--color-neo-border)] p-4 bg-[var(--color-neo-card)]">
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about the codebase..."
            disabled={isLoading || isLoadingConversation || connectionStatus !== 'connected'}
            className="
              flex-1
              neo-input
              resize-none
              min-h-[44px]
              max-h-[120px]
              py-2.5
            "
            rows={1}
          />
          <button
            onClick={handleSend}
            disabled={!inputValue.trim() || isLoading || isLoadingConversation || connectionStatus !== 'connected'}
            className="
              neo-btn neo-btn-primary
              px-4
              disabled:opacity-50 disabled:cursor-not-allowed
            "
            title="Send message"
          >
            {isLoading ? (
              <Loader2 size={18} className="animate-spin" />
            ) : (
              <Send size={18} />
            )}
          </button>
        </div>
        <p className="text-xs text-[var(--color-neo-text-secondary)] mt-2">
          Press Enter to send, Shift+Enter for new line
        </p>
      </div>
    </div>
  )
}
