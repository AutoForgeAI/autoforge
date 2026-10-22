/**
 * Expand Project Chat Component
 *
 * Full chat interface for interactive project expansion with Claude.
 * Allows users to describe new features in natural language.
 *
 * In 'onboard' mode Claude first analyzes an existing codebase, writes the
 * app spec, and records existing functionality before planning new features.
 */

import { useCallback, useEffect, useRef, useState } from 'react'
import { Send, X, CheckCircle2, AlertCircle, Wifi, WifiOff, RotateCcw, Paperclip, Plus, FileText } from 'lucide-react'
import { useExpandChat, type ExpandChatMode } from '../hooks/useExpandChat'
import { ChatMessage } from './ChatMessage'
import { TypingIndicator } from './TypingIndicator'
import type { FileAttachment } from '../lib/types'
import { ALL_ALLOWED_MIME_TYPES, IMAGE_MIME_TYPES, isImageAttachment, resolveMimeType } from '../lib/types'
import { isSubmitEnter } from '../lib/keyboard'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'

// File upload validation constants
const MAX_IMAGE_SIZE = 5 * 1024 * 1024 // 5 MB for images
const MAX_DOCUMENT_SIZE = 20 * 1024 * 1024 // 20 MB for documents
const ALLOWED_EXTENSIONS = ['md', 'txt', 'csv', 'docx', 'xlsx', 'pdf', 'pptx', 'jpg', 'jpeg', 'png']

interface ExpandProjectChatProps {
  projectName: string
  mode?: ExpandChatMode
  onComplete: (featuresAdded: number) => void
  onCancel: () => void
}

export function ExpandProjectChat({
  projectName,
  mode = 'expand',
  onComplete,
  onCancel,
}: ExpandProjectChatProps) {
  const [input, setInput] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pendingAttachments, setPendingAttachments] = useState<FileAttachment[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const isOnboard = mode === 'onboard'

  // Memoize error handler to keep hook dependencies stable
  const handleError = useCallback((err: string) => setError(err), [])

  const {
    messages,
    isLoading,
    isComplete,
    connectionStatus,
    featuresCreated,
    start,
    sendMessage,
    disconnect,
  } = useExpandChat({
    projectName,
    mode,
    onComplete,
    onError: handleError,
  })

  // Start the chat session when component mounts
  useEffect(() => {
    start()

    return () => {
      disconnect()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  // Focus input when not loading
  useEffect(() => {
    if (!isLoading && inputRef.current) {
      inputRef.current.focus()
    }
  }, [isLoading])

  const handleSendMessage = () => {
    const trimmed = input.trim()
    // Allow sending if there's text OR attachments
    if ((!trimmed && pendingAttachments.length === 0) || isLoading) return

    sendMessage(trimmed, pendingAttachments.length > 0 ? pendingAttachments : undefined)
    setInput('')
    setPendingAttachments([]) // Clear attachments after sending
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (isSubmitEnter(e)) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  // File handling for attachments (images and documents)
  const handleFileSelect = useCallback((files: FileList | null) => {
    if (!files) return

    Array.from(files).forEach((file) => {
      // Resolve MIME type (browsers may not set it for .md files)
      let mimeType = file.type
      if (!mimeType || !ALL_ALLOWED_MIME_TYPES.includes(mimeType)) {
        mimeType = resolveMimeType(file.name)
      }

      // Validate file type
      if (!ALL_ALLOWED_MIME_TYPES.includes(mimeType)) {
        const ext = file.name.split('.').pop()?.toLowerCase()
        if (!ext || !ALLOWED_EXTENSIONS.includes(ext)) {
          setError(`Unsupported file type: ${file.name}. Supported: images (JPEG, PNG) and documents (MD, TXT, CSV, DOCX, XLSX, PDF, PPTX).`)
          return
        }
        mimeType = resolveMimeType(file.name)
      }

      // Validate size based on type
      const isImage = (IMAGE_MIME_TYPES as readonly string[]).includes(mimeType)
      const maxSize = isImage ? MAX_IMAGE_SIZE : MAX_DOCUMENT_SIZE
      const maxLabel = isImage ? '5 MB' : '20 MB'
      if (file.size > maxSize) {
        setError(`File too large: ${file.name}. Maximum size is ${maxLabel}.`)
        return
      }

      // Read and convert to base64
      const reader = new FileReader()
      reader.onload = (e) => {
        const dataUrl = e.target?.result as string
        const base64Data = dataUrl.split(',')[1]

        const attachment: FileAttachment = {
          id: `${Date.now()}-${Math.random().toString(36).substring(2, 9)}`,
          filename: file.name,
          mimeType: mimeType as FileAttachment['mimeType'],
          base64Data,
          previewUrl: isImage ? dataUrl : '',
          size: file.size,
        }

        setPendingAttachments((prev) => [...prev, attachment])
      }
      reader.onerror = () => {
        setError(`Failed to read file: ${file.name}`)
      }
      reader.readAsDataURL(file)
    })
  }, [])

  const handleRemoveAttachment = useCallback((id: string) => {
    setPendingAttachments((prev) => prev.filter((a) => a.id !== id))
  }, [])

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault()
      handleFileSelect(e.dataTransfer.files)
    },
    [handleFileSelect]
  )

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
  }, [])

  // Connection status indicator
  const ConnectionIndicator = () => {
    switch (connectionStatus) {
      case 'connected':
        return (
          <span className="flex items-center gap-1 text-xs text-green-500">
            <Wifi size={12} />
            Connected
          </span>
        )
      case 'connecting':
        return (
          <span className="flex items-center gap-1 text-xs text-yellow-500">
            <Wifi size={12} className="animate-pulse" />
            Connecting...
          </span>
        )
      case 'error':
        return (
          <span className="flex items-center gap-1 text-xs text-destructive">
            <WifiOff size={12} />
            Error
          </span>
        )
      default:
        return (
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <WifiOff size={12} />
            Disconnected
          </span>
        )
    }
  }

  return (
    <div className="flex flex-col h-full bg-background">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b-2 border-border bg-card">
        <div className="flex items-center gap-3">
          <h2 className="font-display font-bold text-lg text-foreground">
            {isOnboard ? 'Import Existing Project' : 'Expand Project'}: {projectName}
          </h2>
          <ConnectionIndicator />
          {featuresCreated > 0 && (
            <span className="flex items-center gap-1 text-sm text-green-500 font-bold">
              <Plus size={14} />
              {featuresCreated} added
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {isComplete && (
            <span className="flex items-center gap-1 text-sm text-green-500 font-bold">
              <CheckCircle2 size={16} />
              Complete
            </span>
          )}

          <Button
            onClick={onCancel}
            variant="ghost"
            size="icon"
            title="Close"
          >
            <X size={20} />
          </Button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <Alert variant="destructive" className="rounded-none border-x-0 border-t-0">
          <AlertCircle size={16} />
          <AlertDescription className="flex-1">{error}</AlertDescription>
          <Button
            onClick={() => setError(null)}
            variant="ghost"
            size="icon"
            className="h-6 w-6"
          >
            <X size={14} />
          </Button>
        </Alert>
      )}

      {/* Messages area */}
      <div className="flex-1 overflow-y-auto py-4">
        {messages.length === 0 && !isLoading && (
          <div className="flex flex-col items-center justify-center h-full text-center p-8">
            <Card className="p-6 max-w-md">
              <CardContent className="p-0">
                <h3 className="font-display font-bold text-lg mb-2">
                  {isOnboard ? 'Starting Project Onboarding' : 'Starting Project Expansion'}
                </h3>
                <p className="text-sm text-muted-foreground">
                  {isOnboard
                    ? 'Connecting to Claude to analyze your existing codebase. Exploring the code can take a minute...'
                    : 'Connecting to Claude to help you add new features to your project...'}
                </p>
                {connectionStatus === 'error' && (
                  <Button
                    onClick={start}
                    className="mt-4"
                    size="sm"
                  >
                    <RotateCcw size={14} />
                    Retry Connection
                  </Button>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}

        {/* Typing indicator */}
        {isLoading && <TypingIndicator />}

        {/* Scroll anchor */}
        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      {!isComplete && (
        <div
          className="p-4 border-t-2 border-border bg-card"
          onDrop={handleDrop}
          onDragOver={handleDragOver}
        >
          {/* Attachment previews */}
          {pendingAttachments.length > 0 && (
            <div className="flex flex-wrap gap-2 mb-3">
              {pendingAttachments.map((attachment) => (
                <div
                  key={attachment.id}
                  className="relative group border-2 border-border p-1 bg-card rounded shadow-sm"
                >
                  {isImageAttachment(attachment) ? (
                    <img
                      src={attachment.previewUrl}
                      alt={attachment.filename}
                      className="w-16 h-16 object-cover rounded"
                    />
                  ) : (
                    <div className="w-16 h-16 flex items-center justify-center bg-muted rounded">
                      <FileText size={24} className="text-muted-foreground" />
                    </div>
                  )}
                  <button
                    onClick={() => handleRemoveAttachment(attachment.id)}
                    className="absolute -top-2 -right-2 bg-destructive text-destructive-foreground rounded-full p-0.5 border-2 border-border hover:scale-110 transition-transform"
                    title="Remove attachment"
                  >
                    <X size={12} />
                  </button>
                  <span className="text-xs truncate block max-w-16 mt-1 text-center text-muted-foreground">
                    {attachment.filename.length > 10
                      ? `${attachment.filename.substring(0, 7)}...`
                      : attachment.filename}
                  </span>
                </div>
              ))}
            </div>
          )}

          <div className="flex gap-3">
            {/* Hidden file input */}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/jpeg,image/png,.md,.txt,.csv,.docx,.xlsx,.pdf,.pptx"
              multiple
              onChange={(e) => handleFileSelect(e.target.files)}
              className="hidden"
            />

            {/* Attach button */}
            <Button
              onClick={() => fileInputRef.current?.click()}
              disabled={connectionStatus !== 'connected'}
              variant="ghost"
              size="icon"
              title="Attach files (images: JPEG/PNG up to 5MB, documents: MD, TXT, CSV, DOCX, XLSX, PDF, PPTX up to 20MB)"
            >
              <Paperclip size={18} />
            </Button>

            <Input
              ref={inputRef}
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                pendingAttachments.length > 0
                  ? 'Add a message with your image(s)...'
                  : isOnboard
                    ? 'Correct my understanding, or describe what to build next...'
                    : 'Describe the features you want to add...'
              }
              className="flex-1"
              disabled={isLoading || connectionStatus !== 'connected'}
            />
            <Button
              onClick={handleSendMessage}
              disabled={
                (!input.trim() && pendingAttachments.length === 0) ||
                isLoading ||
                connectionStatus !== 'connected'
              }
              className="px-6"
            >
              <Send size={18} />
            </Button>
          </div>

          {/* Help text */}
          <p className="text-xs text-muted-foreground mt-2">
            Press Enter to send. Drag & drop or click <Paperclip size={12} className="inline" /> to attach files.
          </p>
        </div>
      )}

      {/* Completion footer */}
      {isComplete && (
        <div className="p-4 border-t-2 border-border bg-green-500 text-white">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckCircle2 size={20} />
              <span className="font-bold">
                Added {featuresCreated} {isOnboard ? '' : 'new '}feature{featuresCreated !== 1 ? 's' : ''}!
              </span>
            </div>
            <Button
              onClick={() => onComplete(featuresCreated)}
              variant="secondary"
            >
              Close
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
