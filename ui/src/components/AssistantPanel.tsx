/**
 * Assistant Panel Component
 *
 * Slide-in panel container for the project assistant chat.
 * Slides in from the right side of the screen.
 * Manages conversation state with localStorage persistence.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { X, Bot } from 'lucide-react'
import { AssistantChat } from './AssistantChat'
import { useConversation } from '../hooks/useConversations'
import type { ChatMessage } from '../lib/types'
import { Button } from '@/components/ui/button'

interface AssistantPanelProps {
  projectName: string
  isOpen: boolean
  onClose: () => void
}

const STORAGE_KEY_PREFIX = 'assistant-conversation-'
const WIDTH_STORAGE_KEY = 'assistant-panel-width'
const DEFAULT_WIDTH = 400
const MIN_WIDTH = 300
const MAX_WIDTH_VW = 90

function getStoredConversationId(projectName: string): number | null {
  try {
    const stored = localStorage.getItem(`${STORAGE_KEY_PREFIX}${projectName}`)
    if (stored) {
      const data = JSON.parse(stored)
      return data.conversationId || null
    }
  } catch {
    // Invalid stored data, ignore
  }
  return null
}

function setStoredConversationId(projectName: string, conversationId: number | null) {
  const key = `${STORAGE_KEY_PREFIX}${projectName}`
  if (conversationId) {
    localStorage.setItem(key, JSON.stringify({ conversationId }))
  } else {
    localStorage.removeItem(key)
  }
}

export function AssistantPanel({ projectName, isOpen, onClose }: AssistantPanelProps) {
  // Load initial conversation ID from localStorage
  const [conversationId, setConversationId] = useState<number | null>(() =>
    getStoredConversationId(projectName)
  )

  // Fetch conversation details when we have an ID
  const {
    data: conversationDetail,
    isLoading: isLoadingConversationQuery,
    error: conversationError,
    refetch: refetchConversation,
  } = useConversation(projectName, conversationId)

  // The chat unmounts while the panel is closed, so messages exchanged since the
  // last fetch (or a response that finished in the background) are missing from
  // the cached conversation. Refetch on every open before resuming the chat.
  const [wasOpen, setWasOpen] = useState(isOpen)
  const [isRefreshingOnOpen, setIsRefreshingOnOpen] = useState(false)
  if (isOpen !== wasOpen) {
    setWasOpen(isOpen)
    if (isOpen && conversationId) {
      setIsRefreshingOnOpen(true)
    }
  }
  useEffect(() => {
    if (!isRefreshingOnOpen) return
    refetchConversation().finally(() => setIsRefreshingOnOpen(false))
  }, [isRefreshingOnOpen, refetchConversation])
  const isLoadingConversation = isLoadingConversationQuery || isRefreshingOnOpen

  // Clear stored conversation ID if it no longer exists (404 error)
  useEffect(() => {
    if (conversationError && conversationId) {
      const message = conversationError.message.toLowerCase()
      // Only clear for 404 errors, not transient network issues
      if (message.includes('not found') || message.includes('404')) {
        console.warn(`Conversation ${conversationId} not found, clearing stored ID`)
        setConversationId(null)
      }
    }
  }, [conversationError, conversationId])

  // Convert API messages to ChatMessage format for the chat component
  const initialMessages: ChatMessage[] | undefined = conversationDetail?.messages.map((msg) => ({
    id: `db-${msg.id}`,
    role: msg.role,
    content: msg.content,
    timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
  }))

  // Persist conversation ID changes to localStorage
  useEffect(() => {
    setStoredConversationId(projectName, conversationId)
  }, [projectName, conversationId])

  // Reset conversation ID when project changes
  useEffect(() => {
    setConversationId(getStoredConversationId(projectName))
  }, [projectName])

  // Handle starting a new chat
  const handleNewChat = useCallback(() => {
    setConversationId(null)
  }, [])

  // Handle selecting a conversation from history
  const handleSelectConversation = useCallback((id: number) => {
    setConversationId(id)
  }, [])

  // Handle when a new conversation is created (from WebSocket)
  const handleConversationCreated = useCallback((id: number) => {
    setConversationId(id)
  }, [])

  // Resizable panel width
  const [panelWidth, setPanelWidth] = useState<number>(() => {
    try {
      const stored = localStorage.getItem(WIDTH_STORAGE_KEY)
      if (stored) return Math.max(MIN_WIDTH, parseInt(stored, 10))
    } catch { /* ignore */ }
    return DEFAULT_WIDTH
  })
  const isResizing = useRef(false)

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isResizing.current = true
    const startX = e.clientX
    const startWidth = panelWidth
    const maxWidth = window.innerWidth * (MAX_WIDTH_VW / 100)

    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizing.current) return
      const delta = startX - e.clientX
      const newWidth = Math.min(maxWidth, Math.max(MIN_WIDTH, startWidth + delta))
      setPanelWidth(newWidth)
    }

    const handleMouseUp = () => {
      isResizing.current = false
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      // Persist width
      setPanelWidth((w) => {
        localStorage.setItem(WIDTH_STORAGE_KEY, String(w))
        return w
      })
    }

    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }, [panelWidth])

  return (
    <>
      {/* Backdrop - click to close */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/20 z-40 transition-opacity duration-300"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Panel */}
      <div
        className={`
          fixed right-0 top-0 bottom-0 z-50
          bg-card
          border-l border-border
          transform transition-transform duration-300 ease-out
          flex flex-col shadow-xl
          ${isOpen ? 'translate-x-0' : 'translate-x-full'}
        `}
        style={{ width: `${panelWidth}px`, maxWidth: `${MAX_WIDTH_VW}vw` }}
        role="dialog"
        aria-label="Project Assistant"
        aria-hidden={!isOpen}
      >
        {/* Resize handle */}
        <div
          className="absolute left-0 top-0 bottom-0 w-1.5 cursor-col-resize z-10 group"
          onMouseDown={handleMouseDown}
        >
          <div className="absolute inset-y-0 left-0 w-0.5 bg-border group-hover:bg-primary transition-colors" />
        </div>

        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-primary text-primary-foreground">
          <div className="flex items-center gap-2">
            <div className="bg-card text-foreground border border-border p-1.5 rounded">
              <Bot size={18} />
            </div>
            <div>
              <h2 className="font-semibold">Project Assistant</h2>
              <p className="text-xs opacity-80 font-mono">{projectName}</p>
            </div>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
            className="text-primary-foreground hover:bg-primary-foreground/20"
            title="Close Assistant (Press A)"
            aria-label="Close Assistant"
          >
            <X size={18} />
          </Button>
        </div>

        {/* Chat area */}
        <div className="flex-1 overflow-hidden">
          {isOpen && (
            <AssistantChat
              projectName={projectName}
              conversationId={conversationId}
              initialMessages={initialMessages}
              isLoadingConversation={isLoadingConversation}
              onNewChat={handleNewChat}
              onSelectConversation={handleSelectConversation}
              onConversationCreated={handleConversationCreated}
            />
          )}
        </div>
      </div>
    </>
  )
}
