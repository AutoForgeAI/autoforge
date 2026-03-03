import { Activity } from 'lucide-react'
import { AgentEmojiAvatar, resolveAgentName } from './AgentAvatar'

interface ActivityItem {
  agentName: string
  thought: string
  timestamp: string
  featureId: number
}

interface ActivityFeedProps {
  activities: ActivityItem[]
  maxItems?: number
  showHeader?: boolean
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)

  if (diffSec < 5) return 'just now'
  if (diffSec < 60) return `${diffSec}s ago`
  if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export function ActivityFeed({ activities, maxItems = 20, showHeader = true }: ActivityFeedProps) {
  const displayedActivities = activities.slice(0, maxItems)

  if (displayedActivities.length === 0) {
    return null
  }

  return (
    <div style={{ fontFamily: "'Inter', sans-serif" }}>
      {showHeader && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
          <Activity size={14} style={{ color: '#6A6A20' }} />
          <span style={{ fontSize: '11px', fontWeight: 700, color: '#6A6A20', textTransform: 'uppercase', letterSpacing: '1px' }}>
            Live Activity
          </span>
          <span style={{ fontSize: '11px', color: '#9A9A60' }}>({displayedActivities.length})</span>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
        {displayedActivities.map((activity, idx) => {
          return (
            <div
              key={`${idx}-${activity.featureId}-${activity.timestamp}`}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                padding: '5px 8px', borderRadius: '4px',
              }}
              onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#FAFAF2' }}
              onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
            >
              {/* Agent avatar */}
              <AgentEmojiAvatar name={activity.agentName} size="xs" />

              {/* Agent name */}
              <span style={{ fontSize: '12px', fontWeight: 700, color: '#1A1A00', whiteSpace: 'nowrap' }}>
                {resolveAgentName(activity.agentName)}
              </span>

              {/* Feature ID */}
              <span style={{
                fontSize: '11px', fontWeight: 600, color: '#7A8A00',
                fontFamily: "'JetBrains Mono', monospace", whiteSpace: 'nowrap',
              }}>
                #{activity.featureId}
              </span>

              {/* Thought (fills remaining space) */}
              <span
                style={{
                  flex: 1, minWidth: 0, fontSize: '11px', color: '#6A6A20',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                }}
                title={activity.thought}
              >
                {activity.thought}
              </span>

              {/* Timestamp */}
              <span style={{
                fontSize: '10px', color: '#9A9A60', whiteSpace: 'nowrap', flexShrink: 0,
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                {formatTimestamp(activity.timestamp)}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
