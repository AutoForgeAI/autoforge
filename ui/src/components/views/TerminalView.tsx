/**
 * Terminal View
 *
 * Full-page terminal with tab management. Owns the terminal lifecycle
 * state (create, rename, close) that was previously embedded in DebugLogViewer.
 * Terminal buffers are preserved across tab switches by rendering all terminals
 * stacked and using CSS transforms to show/hide the active one.
 */

import { useState, useCallback, useEffect } from 'react'
import { useAppContext } from '@/contexts/AppContext'
import { Terminal } from '../Terminal'
import { TerminalTabs } from '../TerminalTabs'
import { listTerminals, createTerminal, renameTerminal, deleteTerminal } from '@/lib/api'
import type { TerminalInfo } from '@/lib/types'

export function TerminalView() {
  const { selectedProject } = useAppContext()

  const projectName = selectedProject ?? ''

  // Terminal management state
  const [terminals, setTerminals] = useState<TerminalInfo[]>([])
  const [activeTerminalId, setActiveTerminalId] = useState<string | null>(null)
  const [isLoadingTerminals, setIsLoadingTerminals] = useState(false)

  // Fetch all terminals for the current project
  const fetchTerminals = useCallback(async () => {
    if (!projectName) return

    setIsLoadingTerminals(true)
    try {
      const terminalList = await listTerminals(projectName)
      setTerminals(terminalList)

      // Default to the first terminal if the active one is gone
      if (terminalList.length > 0) {
        setActiveTerminalId(prev => {
          if (!prev || !terminalList.find(t => t.id === prev)) {
            return terminalList[0].id
          }
          return prev
        })
      }
    } catch (err) {
      console.error('Failed to fetch terminals:', err)
    } finally {
      setIsLoadingTerminals(false)
    }
  }, [projectName])

  // Create a new terminal session
  const handleCreateTerminal = useCallback(async () => {
    if (!projectName) return

    try {
      const newTerminal = await createTerminal(projectName)
      setTerminals(prev => [...prev, newTerminal])
      setActiveTerminalId(newTerminal.id)
    } catch (err) {
      console.error('Failed to create terminal:', err)
    }
  }, [projectName])

  // Rename an existing terminal
  const handleRenameTerminal = useCallback(
    async (terminalId: string, newName: string) => {
      if (!projectName) return

      try {
        const updated = await renameTerminal(projectName, terminalId, newName)
        setTerminals(prev =>
          prev.map(t => (t.id === terminalId ? updated : t)),
        )
      } catch (err) {
        console.error('Failed to rename terminal:', err)
      }
    },
    [projectName],
  )

  // Close a terminal (minimum one must remain)
  const handleCloseTerminal = useCallback(
    async (terminalId: string) => {
      if (!projectName || terminals.length <= 1) return

      try {
        await deleteTerminal(projectName, terminalId)
        setTerminals(prev => prev.filter(t => t.id !== terminalId))

        // If the closed terminal was active, switch to the first remaining one
        if (activeTerminalId === terminalId) {
          const remaining = terminals.filter(t => t.id !== terminalId)
          if (remaining.length > 0) {
            setActiveTerminalId(remaining[0].id)
          }
        }
      } catch (err) {
        console.error('Failed to close terminal:', err)
      }
    },
    [projectName, terminals, activeTerminalId],
  )

  // Re-fetch terminals whenever the project changes
  useEffect(() => {
    if (projectName) {
      fetchTerminals()
    } else {
      setTerminals([])
      setActiveTerminalId(null)
    }
  }, [projectName]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
      {/* Tab bar */}
      {terminals.length > 0 && (
        <TerminalTabs
          terminals={terminals}
          activeTerminalId={activeTerminalId}
          onSelect={setActiveTerminalId}
          onCreate={handleCreateTerminal}
          onRename={handleRenameTerminal}
          onClose={handleCloseTerminal}
        />
      )}

      {/* Terminal content area */}
      <div className="flex-1 min-h-0 relative">
        {isLoadingTerminals ? (
          <div className="h-full flex items-center justify-center text-muted-foreground font-mono text-sm">
            Loading terminals...
          </div>
        ) : terminals.length === 0 ? (
          <div className="h-full flex items-center justify-center text-muted-foreground font-mono text-sm">
            No terminal available
          </div>
        ) : (
          /*
           * Render all terminals stacked on top of each other.
           * The active terminal is visible and receives input.
           * Inactive terminals are moved off-screen with `transform` so
           * xterm.js IntersectionObserver pauses rendering while preserving
           * the terminal buffer contents.
           */
          terminals.map(terminal => {
            const isActive = terminal.id === activeTerminalId
            return (
              <div
                key={terminal.id}
                className="absolute inset-0"
                style={{
                  zIndex: isActive ? 10 : 1,
                  transform: isActive ? 'none' : 'translateX(-200%)',
                  pointerEvents: isActive ? 'auto' : 'none',
                }}
              >
                <Terminal
                  projectName={projectName}
                  terminalId={terminal.id}
                  isActive={isActive}
                />
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
