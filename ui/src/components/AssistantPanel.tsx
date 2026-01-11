/**
 * Architect Assistant Panel Component
 *
 * Slide-in panel container for the Architect Assistant chat.
 * The Architect Assistant is the central command hub for project management.
 * Slides in from the right side of the screen.
 */

import { X, Cpu } from 'lucide-react'
import { AssistantChat } from './AssistantChat'

interface AssistantPanelProps {
  projectName: string
  isOpen: boolean
  onClose: () => void
  agentStatus?: 'running' | 'paused' | 'stopped'
}

export function AssistantPanel({ projectName, isOpen, onClose, agentStatus = 'stopped' }: AssistantPanelProps) {
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
          w-[450px] max-w-[90vw]
          bg-white
          border-l-4 border-[var(--color-neo-border)]
          shadow-[-8px_0_0px_rgba(0,0,0,1)]
          transform transition-transform duration-300 ease-out
          flex flex-col
          ${isOpen ? 'translate-x-0' : 'translate-x-full'}
        `}
        role="dialog"
        aria-label="Architect Assistant"
        aria-hidden={!isOpen}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b-3 border-[var(--color-neo-border)] bg-gradient-to-r from-[var(--color-neo-accent)] to-purple-600">
          <div className="flex items-center gap-3">
            <div className="bg-white border-2 border-[var(--color-neo-border)] p-2 shadow-[2px_2px_0px_rgba(0,0,0,1)]">
              <Cpu size={20} className="text-[var(--color-neo-accent)]" />
            </div>
            <div>
              <h2 className="font-display font-bold text-white text-lg">Architect Assistant</h2>
              <p className="text-xs text-white/80 font-mono">{projectName}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="
              neo-btn neo-btn-ghost
              p-2
              bg-white/20 border-white/40
              hover:bg-white/30
              text-white
            "
            title="Close Assistant (Press A)"
            aria-label="Close Assistant"
          >
            <X size={18} />
          </button>
        </div>

        {/* Chat area */}
        <div className="flex-1 overflow-hidden">
          {isOpen && <AssistantChat projectName={projectName} agentStatus={agentStatus} />}
        </div>
      </div>
    </>
  )
}
