import { useState } from 'react'
import { ChevronDown, ChevronUp, Code, FlaskConical, Clock, Lock, Sparkles } from 'lucide-react'
import type { OrchestratorStatus, OrchestratorState } from '../lib/types'
import { AgentEmojiAvatar } from './AgentAvatar'

interface OrchestratorStatusCardProps {
  status: OrchestratorStatus
}

function getStateText(state: OrchestratorState): string {
  switch (state) {
    case 'idle':
      return 'Standing by...'
    case 'initializing':
      return 'Zeus awakens...'
    case 'scheduling':
      return 'Consulting the Fates...'
    case 'spawning':
      return 'Marshalling divine forces...'
    case 'monitoring':
      return 'Watching from the heavens...'
    case 'complete':
      return 'The quest is complete!'
    case 'draining':
      return 'Recalling the forces...'
    case 'paused':
      return 'The gods rest...'
    default:
      return 'Commanding the pantheon...'
  }
}

function getStateDotColor(state: OrchestratorState): string {
  switch (state) {
    case 'complete':
      return '#BBCB64'
    case 'spawning':
    case 'scheduling':
    case 'monitoring':
      return '#7A8A00'
    case 'initializing':
      return '#F79A19'
    case 'draining':
      return '#A05A00'
    case 'paused':
    default:
      return '#6A6A20'
  }
}

function formatRelativeTime(timestamp: string): string {
  const now = new Date()
  const then = new Date(timestamp)
  const diffMs = now.getTime() - then.getTime()
  const diffSecs = Math.floor(diffMs / 1000)

  if (diffSecs < 5) return 'just now'
  if (diffSecs < 60) return `${diffSecs}s ago`
  const diffMins = Math.floor(diffSecs / 60)
  if (diffMins < 60) return `${diffMins}m ago`
  return `${Math.floor(diffMins / 60)}h ago`
}

export function OrchestratorStatusCard({ status }: OrchestratorStatusCardProps) {
  const [showEvents, setShowEvents] = useState(false)
  const dotColor = getStateDotColor(status.state)

  return (
    <div style={{ fontFamily: "'Inter', sans-serif" }}>
      {/* Inline status banner */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
        <span style={{
          width: '10px', height: '10px', borderRadius: '50%',
          background: dotColor, flexShrink: 0,
          boxShadow: `0 0 6px ${dotColor}60`,
        }} />
        <AgentEmojiAvatar name="Zeus" size="sm" />
        <span style={{ fontSize: '16px', fontWeight: 700, color: '#1A1A00' }}>
          Zeus, Commander
        </span>
        <span style={{ fontSize: '13px', color: '#6A6A20' }}>&middot;</span>
        <span style={{ fontSize: '13px', fontWeight: 600, color: dotColor }}>
          {getStateText(status.state)}
        </span>

        {status.recentEvents.length > 0 && (
          <button
            onClick={() => setShowEvents(!showEvents)}
            style={{
              marginLeft: 'auto',
              display: 'flex', alignItems: 'center', gap: '4px',
              fontSize: '12px', fontWeight: 700, color: '#7A8A00',
              background: 'transparent', border: 'none', cursor: 'pointer',
              padding: '4px 8px', borderRadius: '4px', flexShrink: 0,
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#F5F8D0' }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
          >
            <Sparkles size={12} />
            Activity
            {showEvents ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>
        )}
      </div>

      {/* Message */}
      {status.message && (
        <p style={{
          fontSize: '13px', color: '#6A6A20', margin: '0 0 12px 20px',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {status.message}
        </p>
      )}

      {/* Stat badges */}
      <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px', marginLeft: '20px' }}>
        <span style={badgeStyle}>
          <Code size={12} />
          Coding: {status.codingAgents}
        </span>
        <span style={badgeStyle}>
          <FlaskConical size={12} />
          Testing: {status.testingAgents}
        </span>
        <span style={badgeStyle}>
          <Clock size={12} />
          Ready: {status.readyCount}
        </span>
        {status.blockedCount > 0 && (
          <span style={{
            ...badgeStyle,
            background: '#FFF0DC', color: '#A05A00', border: '1px solid #F0C880',
          }}>
            <Lock size={12} />
            Blocked: {status.blockedCount}
          </span>
        )}
      </div>

      {/* Expandable events */}
      {showEvents && status.recentEvents.length > 0 && (
        <div style={{ marginTop: '12px', marginLeft: '20px', paddingTop: '10px', borderTop: '1px solid #DDEC90' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
            {status.recentEvents.map((event, idx) => (
              <div
                key={`${event.timestamp}-${idx}`}
                style={{ display: 'flex', alignItems: 'flex-start', gap: '8px', fontSize: '12px' }}
              >
                <span style={{ color: '#7A8A00', flexShrink: 0, fontFamily: "'JetBrains Mono', monospace", fontSize: '11px' }}>
                  {formatRelativeTime(event.timestamp)}
                </span>
                <span style={{ color: '#1A1A00' }}>
                  {event.message}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

const badgeStyle: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: '4px',
  fontSize: '12px', fontWeight: 700, padding: '3px 10px', borderRadius: '20px',
  background: '#F5F8D0', color: '#7A8A00', border: '1px solid #DDEC90',
}
