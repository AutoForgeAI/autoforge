/**
 * Assistant View
 *
 * Full-page project assistant chat view with conversation management.
 * Reuses the same conversation persistence and lifecycle logic as
 * AssistantPanel, but renders inline rather than as a slide-in overlay.
 */

import { useState, useEffect, useCallback } from 'react'
import { useAppContext } from '@/contexts/AppContext'
import { AssistantChat } from '../AssistantChat'
import { useConversation } from '@/hooks/useConversations'
import { Bot } from 'lucide-react'
import type { ChatMessage } from '@/lib/types'

const STORAGE_KEY_PREFIX = 'assistant-conversation-'

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

export function AssistantView() {
  const { selectedProject } = useAppContext()

  const projectName = selectedProject ?? ''

  // Load the last-used conversation ID from localStorage
  const [conversationId, setConversationId] = useState<number | null>(() =>
    getStoredConversationId(projectName),
  )

  // Fetch conversation details when we have a valid ID
  const {
    data: conversationDetail,
    isLoading: isLoadingConversation,
    error: conversationError,
  } = useConversation(projectName || null, conversationId)

  // Clear stored conversation ID on 404 (conversation was deleted or never existed)
  useEffect(() => {
    if (conversationError && conversationId) {
      const message = conversationError.message.toLowerCase()
      if (message.includes('not found') || message.includes('404')) {
        console.warn(`Conversation ${conversationId} not found, clearing stored ID`)
        setConversationId(null)
      }
    }
  }, [conversationError, conversationId])

  // Convert API message format to the ChatMessage format expected by AssistantChat
  const initialMessages: ChatMessage[] | undefined = conversationDetail?.messages.map(msg => ({
    id: `db-${msg.id}`,
    role: msg.role,
    content: msg.content,
    timestamp: msg.timestamp ? new Date(msg.timestamp) : new Date(),
  }))

  // Persist conversation ID changes to localStorage
  useEffect(() => {
    if (projectName) {
      setStoredConversationId(projectName, conversationId)
    }
  }, [projectName, conversationId])

  // Reset conversation ID when the project changes
  useEffect(() => {
    setConversationId(getStoredConversationId(projectName))
  }, [projectName])

  // Start a brand-new chat
  const handleNewChat = useCallback(() => {
    setConversationId(null)
  }, [])

  // Select a conversation from the history list
  const handleSelectConversation = useCallback((id: number) => {
    setConversationId(id)
  }, [])

  // WebSocket notifies us that a new conversation was created
  const handleConversationCreated = useCallback((id: number) => {
    setConversationId(id)
  }, [])

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border bg-primary text-primary-foreground">
        <div className="bg-card text-foreground border border-border p-1.5 rounded">
          <Bot size={18} />
        </div>
        <div>
          <h2 className="font-semibold">Project Assistant</h2>
          {projectName && (
            <p className="text-xs opacity-80 font-mono">{projectName}</p>
          )}
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-hidden">
        {projectName && (
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
  )
}
