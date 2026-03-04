import React, { useState, useEffect, useCallback } from 'react'
import { DEFAULT_PROMPTS, QUICK_INSERT_ITEMS } from './agentPrompts/index'

type RoleBadge = 'LEAD' | 'INT' | 'SPC'

interface AgentData {
  name: string
  subtitle: string
  role: RoleBadge
  status: 'working' | 'idle'
  emoji: string
  tasks: number
  capabilities: string[]
  model: string
  tokensUsed: string
  uptime: string
  successRate: string
  avgResponseTime: string
  assignedProjects: string[]
  recentActivity: { action: string; time: string; project?: string }[]
}

const AGENTS: AgentData[] = [
  { name: 'Zeus', subtitle: 'Chief Orchestrator', role: 'LEAD', status: 'working', emoji: '\u26A1', tasks: 4, capabilities: ['Project routing', 'Agent orchestration', 'Decision making', 'HITL escalation'], model: 'Claude Opus 4.6', tokensUsed: '20.2M', uptime: '99.8%', successRate: '97%', avgResponseTime: '1.2s', assignedProjects: ['Alpha Rewrite', 'Portal Modernization', 'Design Rebuild'], recentActivity: [{ action: 'Routed task to Athena', time: '2m ago', project: 'Alpha Rewrite' }, { action: 'Escalated HITL review', time: '8m ago', project: 'Portal Modernization' }] },
  { name: 'Athena', subtitle: 'Strategy & Architecture', role: 'INT', status: 'working', emoji: '\uD83E\uDDE0', tasks: 3, capabilities: ['Code generation', 'Refactoring', 'TypeScript', 'API design'], model: 'Claude Sonnet 4.5', tokensUsed: '31.9M', uptime: '99.5%', successRate: '94%', avgResponseTime: '3.8s', assignedProjects: ['Alpha Rewrite', 'CRM Integration'], recentActivity: [{ action: 'Committed auth module', time: '1m ago', project: 'Alpha Rewrite' }, { action: 'Refactored API layer', time: '12m ago', project: 'Alpha Rewrite' }] },
  { name: 'Apollo', subtitle: 'Code Generation', role: 'SPC', status: 'working', emoji: '\u2600\uFE0F', tasks: 2, capabilities: ['User research', 'Data analysis', 'Persona mapping'], model: 'Claude Haiku 4.5', tokensUsed: '5.1M', uptime: '99.9%', successRate: '98%', avgResponseTime: '0.8s', assignedProjects: ['Portal Modernization'], recentActivity: [{ action: 'Generated persona report', time: '5m ago', project: 'Portal Modernization' }] },
  { name: 'Hermes', subtitle: 'Integration & Delivery', role: 'INT', status: 'working', emoji: '\uD83D\uDC65', tasks: 1, capabilities: ['Churn analysis', 'Re-engagement', 'Health scoring'], model: 'Claude Haiku 4.5', tokensUsed: '3.2M', uptime: '99.7%', successRate: '96%', avgResponseTime: '1.0s', assignedProjects: ['CRM Integration'], recentActivity: [{ action: 'Updated health scores', time: '3m ago', project: 'CRM Integration' }] },
  { name: 'Artemis', subtitle: 'Testing & QA', role: 'SPC', status: 'working', emoji: '\uD83C\uDFAF', tasks: 2, capabilities: ['Lead discovery', 'Signal detection', 'Qualification'], model: 'Claude Haiku 4.5', tokensUsed: '4.8M', uptime: '99.6%', successRate: '91%', avgResponseTime: '1.5s', assignedProjects: ['Alpha Rewrite', 'Legacy API Migration'], recentActivity: [{ action: 'Validated endpoint schema', time: '6m ago', project: 'Legacy API Migration' }] },
  { name: 'Hephaestus', subtitle: 'Infrastructure & Build', role: 'LEAD', status: 'working', emoji: '\uD83D\uDD28', tasks: 3, capabilities: ['Task delegation', 'QA oversight', 'Progress reporting'], model: 'Claude Opus 4.6', tokensUsed: '15.9M', uptime: '99.9%', successRate: '99%', avgResponseTime: '1.1s', assignedProjects: ['Alpha Rewrite', 'Design Rebuild', 'Mobile Proto'], recentActivity: [{ action: 'Delegated build tasks', time: '1m ago', project: 'Alpha Rewrite' }] },
  { name: 'Ares', subtitle: 'Security & Compliance', role: 'SPC', status: 'working', emoji: '\uD83D\uDEE1\uFE0F', tasks: 2, capabilities: ['Copywriting', 'Documentation', 'Schema writing'], model: 'Claude Sonnet 4.5', tokensUsed: '10.1M', uptime: '99.4%', successRate: '95%', avgResponseTime: '2.4s', assignedProjects: ['Alpha Rewrite', 'Dashboard Overhaul'], recentActivity: [{ action: 'Updated API docs', time: '4m ago', project: 'Alpha Rewrite' }] },
]

const ROLE_STYLES: Record<RoleBadge, { bg: string; color: string; border: string }> = {
  LEAD: { bg: '#FFF0DC', color: '#A05A00', border: '#F0C880' },
  INT: { bg: '#F5F8D0', color: '#7A8A00', border: '#DDEC90' },
  SPC: { bg: '#F5F8D0', color: '#7A8A00', border: '#DDEC90' },
}

const ROLE_LABELS: Record<RoleBadge, string> = {
  LEAD: 'Lead Agent',
  INT: 'Integration Agent',
  SPC: 'Specialist Agent',
}

function RosterDrawer({ agent, onClose }: { agent: AgentData; onClose: () => void }) {
  const [visible, setVisible] = useState(false)
  const [view, setView] = useState<'detail' | 'configure'>('detail')
  const [promptText, setPromptText] = useState(() => DEFAULT_PROMPTS[agent.name] || '')
  const [saved, setSaved] = useState(false)
  const roleStyle = ROLE_STYLES[agent.role]
  const isIdle = agent.status === 'idle'

  useEffect(() => {
    requestAnimationFrame(() => setVisible(true))
  }, [])

  const handleClose = () => {
    setVisible(false)
    setTimeout(onClose, 250)
  }

  const handleSave = useCallback(() => {
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }, [])

  const sectionTitle: React.CSSProperties = {
    fontSize: '11px', fontWeight: 700, letterSpacing: '1.5px', textTransform: 'uppercase',
    color: '#7A8A00', marginBottom: '10px', paddingBottom: '6px', borderBottom: '1px solid #F5F8D0',
  }

  const metricBox: React.CSSProperties = {
    background: '#FAFAF2', border: '1px solid #DDEC90', borderRadius: '6px', padding: '10px 12px',
  }

  return (
    <>
      <div
        onClick={handleClose}
        style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.25)', zIndex: 998,
          opacity: visible ? 1 : 0, transition: 'opacity 0.25s ease',
        }}
      />

      <div
        style={{
          position: 'fixed', top: 0, right: 0, bottom: 0, width: view === 'configure' ? '560px' : '420px', zIndex: 999,
          background: '#FFFFFF', borderLeft: '1px solid #DDEC90',
          boxShadow: '-8px 0 30px rgba(0,0,0,0.08)',
          transform: visible ? 'translateX(0)' : 'translateX(100%)',
          transition: 'transform 0.25s ease, width 0.25s ease',
          display: 'flex', flexDirection: 'column',
          fontFamily: "'Inter', sans-serif",
        }}
      >
        {/* Header */}
        <div style={{
          padding: '20px 24px', borderBottom: '1px solid #DDEC90', background: '#FAFAF2',
          display: 'flex', alignItems: 'flex-start', gap: '14px', flexShrink: 0,
        }}>
          <div style={{
            width: '56px', height: '56px', borderRadius: '12px',
            border: '2px solid #DDEC90', background: '#FFFFFF',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: '28px', flexShrink: 0,
          }}>
            {agent.emoji}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
              <span style={{ fontSize: '20px', fontWeight: 700, color: '#1A1A00' }}>{agent.name}</span>
              <span style={{
                fontSize: '10px', fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase',
                borderRadius: '20px', padding: '2px 8px',
                background: roleStyle.bg, color: roleStyle.color, border: `1px solid ${roleStyle.border}`,
              }}>
                {agent.role}
              </span>
            </div>
            <div style={{ fontSize: '14px', color: '#6A6A20', marginBottom: '6px' }}>{agent.subtitle}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '7px', height: '7px', borderRadius: '50%', background: isIdle ? '#E0E0E0' : '#BBCB64' }} />
              <span style={{ fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', color: isIdle ? '#6A6A20' : '#BBCB64' }}>
                {isIdle ? 'Idle' : 'Working'}
              </span>
              <span style={{ fontSize: '12px', color: '#6A6A20' }}>&middot; {agent.tasks} active task{agent.tasks !== 1 ? 's' : ''}</span>
            </div>
          </div>
          <button
            onClick={handleClose}
            style={{
              width: '28px', height: '28px', borderRadius: '6px', border: '1px solid #DDEC90',
              background: 'transparent', cursor: 'pointer', display: 'flex', alignItems: 'center',
              justifyContent: 'center', fontSize: '16px', color: '#6A6A20', flexShrink: 0,
              transition: 'background 0.12s',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#F5F8D0' }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
          >
            &times;
          </button>
        </div>

        {/* Tab bar */}
        <div style={{ display: 'flex', borderBottom: '1px solid #DDEC90', background: '#FFFFFF', flexShrink: 0 }}>
          {([{ id: 'detail' as const, label: 'Overview' }, { id: 'configure' as const, label: 'System Prompt' }]).map(tab => (
            <button
              key={tab.id}
              onClick={() => setView(tab.id)}
              style={{
                flex: 1, padding: '10px 16px', fontSize: '12px', fontWeight: 700,
                letterSpacing: '0.5px', textTransform: 'uppercase',
                background: 'transparent', border: 'none', cursor: 'pointer',
                color: view === tab.id ? '#7A8A00' : '#6A6A20',
                borderBottom: view === tab.id ? '2px solid #7A8A00' : '2px solid transparent',
                transition: 'all 0.15s',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Detail view */}
        {view === 'detail' && (
          <>
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
              <div style={sectionTitle}>Performance Metrics</div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '24px' }}>
                {[
                  { label: 'Model', value: agent.model },
                  { label: 'Tokens Used (MTD)', value: agent.tokensUsed },
                  { label: 'Uptime', value: agent.uptime },
                  { label: 'Success Rate', value: agent.successRate },
                  { label: 'Avg Response', value: agent.avgResponseTime },
                  { label: 'Role Type', value: ROLE_LABELS[agent.role] },
                ].map(m => (
                  <div key={m.label} style={metricBox}>
                    <div style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase', color: '#7A8A00', marginBottom: '4px' }}>{m.label}</div>
                    <div style={{ fontSize: '15px', fontWeight: 700, color: '#1A1A00' }}>{m.value}</div>
                  </div>
                ))}
              </div>

              <div style={sectionTitle}>Capabilities</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '24px' }}>
                {agent.capabilities.map(cap => (
                  <span key={cap} style={{ fontSize: '12px', padding: '4px 10px', borderRadius: '20px', background: '#F5F8D0', color: '#1A1A00', border: '1px solid #DDEC90', fontWeight: 600 }}>{cap}</span>
                ))}
              </div>

              <div style={sectionTitle}>Assigned Projects</div>
              {agent.assignedProjects.length === 0 ? (
                <div style={{ fontSize: '13px', color: '#6A6A20', marginBottom: '24px', fontStyle: 'italic' }}>No active project assignments</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '24px' }}>
                  {agent.assignedProjects.map(p => (
                    <div key={p} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px', background: '#FAFAF2', borderRadius: '6px', border: '1px solid #F5F8D0' }}>
                      <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#BBCB64', flexShrink: 0 }} />
                      <span style={{ fontSize: '13px', fontWeight: 600, color: '#1A1A00' }}>{p}</span>
                    </div>
                  ))}
                </div>
              )}

              <div style={sectionTitle}>Recent Activity</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
                {agent.recentActivity.map((act, idx) => (
                  <div key={idx} style={{ display: 'flex', gap: '12px', padding: '10px 0', borderBottom: idx < agent.recentActivity.length - 1 ? '1px solid #F5F8D0' : 'none' }}>
                    <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#BBCB64', marginTop: '5px', flexShrink: 0 }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: '13px', fontWeight: 600, color: '#1A1A00' }}>{act.action}</div>
                      <div style={{ fontSize: '11px', color: '#6A6A20', marginTop: '2px' }}>
                        {act.time}{act.project && <> &middot; <span style={{ color: '#7A8A00' }}>{act.project}</span></>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div style={{ padding: '16px 24px', borderTop: '1px solid #DDEC90', background: '#FAFAF2', display: 'flex', gap: '10px', flexShrink: 0 }}>
              <button
                style={{ flex: 1, fontSize: '13px', fontWeight: 700, color: '#7A8A00', border: '1px solid #DDEC90', background: 'transparent', borderRadius: '6px', padding: '10px 16px', cursor: 'pointer', transition: 'background 0.12s' }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#F5F8D0' }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
              >
                View Logs
              </button>
              <button
                onClick={() => setView('configure')}
                style={{ flex: 1, fontSize: '13px', fontWeight: 700, color: '#1A1A00', background: '#BBCB64', border: 'none', borderRadius: '6px', padding: '10px 16px', cursor: 'pointer', transition: 'opacity 0.12s' }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.opacity = '0.9' }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.opacity = '1' }}
              >
                Configure
              </button>
            </div>
          </>
        )}

        {/* Configure view */}
        {view === 'configure' && (
          <>
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', padding: '12px 14px', borderRadius: '8px', background: '#FAFAF2', border: '1px solid #DDEC90' }}>
                <span style={{ fontSize: '16px', flexShrink: 0, marginTop: '1px' }}>&#9889;</span>
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 700, color: '#1A1A00', marginBottom: '3px' }}>Agent System Prompt</div>
                  <div style={{ fontSize: '12px', color: '#6A6A20', lineHeight: 1.5 }}>
                    This prompt defines how <strong>{agent.name}</strong> behaves. Edit to customize personality, constraints, and focus areas.
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '10px' }}>
                {[
                  { label: 'Model', value: agent.model },
                  { label: 'Characters', value: promptText.length.toLocaleString() },
                  { label: 'Lines', value: String(promptText.split('\n').length) },
                ].map(m => (
                  <div key={m.label} style={{ flex: 1, padding: '8px 12px', borderRadius: '6px', background: '#F5F8D0', border: '1px solid #DDEC90' }}>
                    <div style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase', color: '#7A8A00', marginBottom: '2px' }}>{m.label}</div>
                    <div style={{ fontSize: '13px', fontWeight: 600, color: '#1A1A00' }}>{m.value}</div>
                  </div>
                ))}
              </div>

              <textarea
                value={promptText}
                onChange={e => setPromptText(e.target.value)}
                spellCheck={false}
                style={{
                  flex: 1, minHeight: '300px',
                  fontFamily: "'JetBrains Mono', 'Consolas', monospace",
                  fontSize: '13px', lineHeight: 1.6, color: '#1A1A00',
                  background: '#FFFFFF', border: '1px solid #DDEC90',
                  borderRadius: '8px', padding: '16px',
                  resize: 'none', outline: 'none', transition: 'border-color 0.15s',
                }}
                onFocus={e => { e.currentTarget.style.borderColor = '#7A8A00' }}
                onBlur={e => { e.currentTarget.style.borderColor = '#DDEC90' }}
              />

              <div>
                <div style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase', color: '#7A8A00', marginBottom: '8px' }}>Quick Insert</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {QUICK_INSERT_ITEMS.map(item => (
                    <button
                      key={item.label}
                      onClick={() => setPromptText(prev => prev + item.text)}
                      style={{ fontSize: '11px', fontWeight: 600, padding: '4px 10px', borderRadius: '20px', background: 'transparent', color: '#7A8A00', border: '1px solid #DDEC90', cursor: 'pointer', transition: 'background 0.12s' }}
                      onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#F5F8D0' }}
                      onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div style={{ padding: '16px 24px', borderTop: '1px solid #DDEC90', background: '#FAFAF2', display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
              <button
                onClick={() => setPromptText(DEFAULT_PROMPTS[agent.name] || '')}
                style={{ fontSize: '12px', fontWeight: 600, color: '#6A6A20', border: '1px solid #DDEC90', background: 'transparent', borderRadius: '6px', padding: '8px 14px', cursor: 'pointer', transition: 'background 0.12s' }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#F5F8D0' }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
              >
                Reset to Default
              </button>
              <div style={{ flex: 1 }} />
              <button
                onClick={() => setView('detail')}
                style={{ fontSize: '13px', fontWeight: 700, color: '#7A8A00', border: '1px solid #DDEC90', background: 'transparent', borderRadius: '6px', padding: '10px 16px', cursor: 'pointer', transition: 'background 0.12s' }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#F5F8D0' }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                style={{ fontSize: '13px', fontWeight: 700, color: saved ? '#FFFFFF' : '#1A1A00', background: saved ? '#7A8A00' : '#BBCB64', border: 'none', borderRadius: '6px', padding: '10px 20px', cursor: 'pointer', transition: 'all 0.2s' }}
                onMouseEnter={e => { if (!saved) (e.currentTarget as HTMLElement).style.opacity = '0.9' }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.opacity = '1' }}
              >
                {saved ? '\u2713 Saved' : 'Save Prompt'}
              </button>
            </div>
          </>
        )}
      </div>
    </>
  )
}

export function AgentRoster() {
  const [hoveredAgent, setHoveredAgent] = useState<string | null>(null)
  const [selectedAgent, setSelectedAgent] = useState<AgentData | null>(null)

  return (
    <div
      style={{
        background: '#FFFFFF',
        border: '1px solid #DDEC90',
        borderRadius: '8px',
        overflow: 'hidden',
        fontFamily: "'Inter', sans-serif",
      }}
    >
      {/* Card header */}
      <div
        style={{
          padding: '12px 16px',
          borderBottom: '1px solid #DDEC90',
          background: '#FAFAF2',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <span style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '2px', textTransform: 'uppercase', color: '#7A8A00' }}>
          Agent Roster
        </span>
        <span
          style={{
            fontSize: '12px',
            fontWeight: 700,
            background: '#F5F8D0',
            color: '#7A8A00',
            border: '1px solid #DDEC90',
            borderRadius: '10px',
            padding: '1px 7px',
          }}
        >
          14 Working
        </span>
      </div>

      {/* Agent List */}
      <div style={{ padding: '14px 16px' }}>
        {AGENTS.map((agent, idx) => (
          <div
            key={agent.name}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              padding: '9px 0',
              borderBottom: idx < AGENTS.length - 1 ? '1px solid #DDEC90' : 'none',
              cursor: 'pointer',
              background: hoveredAgent === agent.name ? '#F5F8D0' : 'transparent',
              borderRadius: '4px',
              transition: 'background 0.12s',
            }}
            onClick={() => setSelectedAgent(agent)}
            onMouseEnter={() => setHoveredAgent(agent.name)}
            onMouseLeave={() => setHoveredAgent(null)}
          >
            {/* Icon box */}
            <div
              style={{
                width: '34px',
                height: '34px',
                borderRadius: '8px',
                border: '1.5px solid #DDEC90',
                background: '#FAFAF2',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '16px',
                flexShrink: 0,
              }}
            >
              {agent.emoji}
            </div>

            {/* Agent info */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ fontSize: '16px', fontWeight: 700, color: '#1A1A00' }}>{agent.name}</span>
                <span
                  style={{
                    fontSize: '10px',
                    fontWeight: 700,
                    letterSpacing: '1px',
                    textTransform: 'uppercase',
                    borderRadius: '10px',
                    padding: '2px 7px',
                    background: ROLE_STYLES[agent.role].bg,
                    color: ROLE_STYLES[agent.role].color,
                    border: `1px solid ${ROLE_STYLES[agent.role].border}`,
                  }}
                >
                  {agent.role}
                </span>
              </div>
              <div style={{ fontSize: '13px', color: '#6A6A20', marginTop: '1px' }}>{agent.subtitle}</div>
              {agent.status === 'working' && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', marginTop: '2px' }}>
                  <span style={{ width: '5px', height: '5px', borderRadius: '50%', background: '#BBCB64', flexShrink: 0 }} />
                  <span style={{ fontSize: '10px', fontWeight: 700, color: '#BBCB64' }}>WORKING</span>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div
        style={{
          padding: '10px 16px',
          borderTop: '1px solid #DDEC90',
          textAlign: 'center',
        }}
      >
        <button
          style={{
            background: 'none',
            border: 'none',
            fontSize: '13px',
            fontWeight: 700,
            color: '#7A8A00',
            cursor: 'pointer',
            padding: '4px 8px',
            borderRadius: '4px',
            transition: 'background 0.12s',
          }}
          onMouseEnter={(e) => { (e.target as HTMLElement).style.background = '#F5F8D0' }}
          onMouseLeave={(e) => { (e.target as HTMLElement).style.background = 'transparent' }}
        >
          View all 16 agents &rarr;
        </button>
      </div>

      {/* Agent Detail Drawer */}
      {selectedAgent && (
        <RosterDrawer agent={selectedAgent} onClose={() => setSelectedAgent(null)} />
      )}
    </div>
  )
}
