import React, { useState, useEffect, useCallback } from 'react'
import { DEFAULT_PROMPTS, QUICK_INSERT_ITEMS } from './agentPrompts/index'

type RoleBadge = 'LEAD' | 'INT' | 'SPC'
type AgentStatus = 'working' | 'idle'

interface AgentData {
  name: string
  role: RoleBadge
  status: AgentStatus
  subtitle: string
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
  systemPrompt?: string
}

const AGENTS: AgentData[] = [
  { name: 'Zeus', role: 'LEAD', status: 'working', subtitle: 'Chief Orchestrator', emoji: '\u26A1', tasks: 4, capabilities: ['Project routing', 'Agent orchestration', 'Decision making', 'HITL escalation'], model: 'Claude Opus 4.6', tokensUsed: '20.2M', uptime: '99.8%', successRate: '97%', avgResponseTime: '1.2s', assignedProjects: ['Alpha Rewrite', 'Portal Modernization', 'Design Rebuild'], recentActivity: [{ action: 'Routed task to Athena', time: '2m ago', project: 'Alpha Rewrite' }, { action: 'Escalated HITL review', time: '8m ago', project: 'Portal Modernization' }, { action: 'Approved deployment', time: '14m ago', project: 'Design Rebuild' }, { action: 'Created sprint plan', time: '32m ago' }] },
  { name: 'Athena', role: 'INT', status: 'working', subtitle: 'Strategy & Architecture', emoji: '\uD83E\uDDE0', tasks: 3, capabilities: ['Code generation', 'Refactoring', 'TypeScript', 'API design'], model: 'Claude Sonnet 4.5', tokensUsed: '31.9M', uptime: '99.5%', successRate: '94%', avgResponseTime: '3.8s', assignedProjects: ['Alpha Rewrite', 'CRM Integration'], recentActivity: [{ action: 'Committed auth module', time: '1m ago', project: 'Alpha Rewrite' }, { action: 'Refactored API layer', time: '12m ago', project: 'Alpha Rewrite' }, { action: 'Fixed type errors', time: '25m ago', project: 'CRM Integration' }] },
  { name: 'Apollo', role: 'SPC', status: 'working', subtitle: 'Code Generation', emoji: '\u2600\uFE0F', tasks: 2, capabilities: ['User research', 'Data analysis', 'Persona mapping'], model: 'Claude Haiku 4.5', tokensUsed: '5.1M', uptime: '99.9%', successRate: '98%', avgResponseTime: '0.8s', assignedProjects: ['Portal Modernization'], recentActivity: [{ action: 'Generated persona report', time: '5m ago', project: 'Portal Modernization' }, { action: 'Analyzed user feedback', time: '18m ago' }] },
  { name: 'Hermes', role: 'SPC', status: 'working', subtitle: 'Integration & Delivery', emoji: '\uD83D\uDC65', tasks: 1, capabilities: ['Churn analysis', 'Re-engagement', 'Health scoring'], model: 'Claude Haiku 4.5', tokensUsed: '3.2M', uptime: '99.7%', successRate: '96%', avgResponseTime: '1.0s', assignedProjects: ['CRM Integration'], recentActivity: [{ action: 'Updated health scores', time: '3m ago', project: 'CRM Integration' }, { action: 'Flagged at-risk accounts', time: '22m ago' }] },
  { name: 'Artemis', role: 'SPC', status: 'working', subtitle: 'Testing & QA', emoji: '\uD83C\uDFAF', tasks: 2, capabilities: ['Lead discovery', 'Signal detection', 'Qualification'], model: 'Claude Haiku 4.5', tokensUsed: '4.8M', uptime: '99.6%', successRate: '91%', avgResponseTime: '1.5s', assignedProjects: ['Alpha Rewrite', 'Legacy API Migration'], recentActivity: [{ action: 'Validated endpoint schema', time: '6m ago', project: 'Legacy API Migration' }, { action: 'Ran integration tests', time: '19m ago', project: 'Alpha Rewrite' }] },
  { name: 'Hephaestus', role: 'LEAD', status: 'working', subtitle: 'Infrastructure & Build', emoji: '\uD83D\uDD28', tasks: 3, capabilities: ['Task delegation', 'QA oversight', 'Progress reporting'], model: 'Claude Opus 4.6', tokensUsed: '15.9M', uptime: '99.9%', successRate: '99%', avgResponseTime: '1.1s', assignedProjects: ['Alpha Rewrite', 'Design Rebuild', 'Mobile Proto'], recentActivity: [{ action: 'Delegated build tasks', time: '1m ago', project: 'Alpha Rewrite' }, { action: 'QA review passed', time: '9m ago', project: 'Design Rebuild' }, { action: 'Generated progress report', time: '30m ago' }] },
  { name: 'Ares', role: 'SPC', status: 'working', subtitle: 'Security & Compliance', emoji: '\uD83D\uDEE1\uFE0F', tasks: 2, capabilities: ['Copywriting', 'Documentation', 'Schema writing'], model: 'Claude Sonnet 4.5', tokensUsed: '10.1M', uptime: '99.4%', successRate: '95%', avgResponseTime: '2.4s', assignedProjects: ['Alpha Rewrite', 'Dashboard Overhaul'], recentActivity: [{ action: 'Updated API docs', time: '4m ago', project: 'Alpha Rewrite' }, { action: 'Wrote changelog', time: '15m ago', project: 'Dashboard Overhaul' }] },
  { name: 'Poseidon', role: 'SPC', status: 'working', subtitle: 'Data & Analytics', emoji: '\uD83C\uDF0A', tasks: 1, capabilities: ['Figma parsing', 'Component mapping', 'Design tokens'], model: 'Claude Sonnet 4.5', tokensUsed: '7.3M', uptime: '99.3%', successRate: '93%', avgResponseTime: '4.2s', assignedProjects: ['Design Rebuild'], recentActivity: [{ action: 'Parsed Figma frames', time: '7m ago', project: 'Design Rebuild' }, { action: 'Extracted design tokens', time: '20m ago', project: 'Design Rebuild' }] },
  { name: 'Hades', role: 'SPC', status: 'idle', subtitle: 'Monitoring & Alerts', emoji: '\uD83D\uDD25', tasks: 0, capabilities: ['Vuln scanning', 'Auth review', 'OWASP checks'], model: 'Claude Opus 4.6', tokensUsed: '1.4M', uptime: '99.9%', successRate: '100%', avgResponseTime: '2.0s', assignedProjects: [], recentActivity: [{ action: 'Completed OWASP scan', time: '1h ago', project: 'Alpha Rewrite' }, { action: 'Reviewed auth flow', time: '3h ago', project: 'Portal Modernization' }] },
]

const ROLE_STYLES: Record<RoleBadge, { bg: string; color: string; border: string }> = {
  LEAD: { bg: '#FFF0DC', color: '#A05A00', border: '#F0C880' },
  INT: { bg: '#F5F8D0', color: '#7A8A00', border: '#DDEC90' },
  SPC: { bg: '#F5F8D0', color: '#7A8A00', border: '#DDEC90' },
}

interface OrchNode {
  emoji: string
  name: string
  sub: string
  running?: boolean
  lead?: boolean
}

interface OrchFlow {
  title: string
  badge: string
  badgeStyle: { bg: string; color: string; border: string }
  nodes: OrchNode[]
}

const ORCH_FLOWS: OrchFlow[] = [
  {
    title: 'Standard Workflow \u2014 Folder Input',
    badge: 'Auto-configured',
    badgeStyle: { bg: '#F5F8D0', color: '#7A8A00', border: '#DDEC90' },
    nodes: [
      { emoji: '\u26A1', name: 'Zeus', sub: 'Ingest & Route', lead: true },
      { emoji: '\uD83E\uDDE0', name: 'Athena', sub: 'Architect', running: true },
      { emoji: '\u2600\uFE0F', name: 'Apollo', sub: 'Code Gen', running: true },
      { emoji: '\uD83D\uDD28', name: 'Hephaestus', sub: 'Build & QA', running: true },
      { emoji: '\uD83D\uDEE1\uFE0F', name: 'Ares', sub: 'Security' },
      { emoji: '\uD83C\uDFAF', name: 'Artemis', sub: 'Validate' },
    ],
  },
  {
    title: 'Figma Input Workflow',
    badge: 'Design-first',
    badgeStyle: { bg: '#EDE4F7', color: '#6B21A8', border: '#D4B8F0' },
    nodes: [
      { emoji: '\u26A1', name: 'Zeus', sub: 'Ingest', lead: true },
      { emoji: '\uD83C\uDF0A', name: 'Poseidon', sub: 'Parse Design', running: true },
      { emoji: '\uD83E\uDDE0', name: 'Athena', sub: 'Architect', running: true },
      { emoji: '\u2600\uFE0F', name: 'Apollo', sub: 'Code Gen', running: true },
      { emoji: '\uD83D\uDD28', name: 'Hephaestus', sub: 'Build & QA' },
    ],
  },
  {
    title: 'Greenfield Project',
    badge: 'From scratch',
    badgeStyle: { bg: '#D1FAE5', color: '#047857', border: '#6EE7B7' },
    nodes: [
      { emoji: '\u26A1', name: 'Zeus', sub: 'Plan & Scaffold', lead: true },
      { emoji: '\uD83E\uDDE0', name: 'Athena', sub: 'Architecture', running: true },
      { emoji: '\u2600\uFE0F', name: 'Apollo', sub: 'Code Gen', running: true },
      { emoji: '\uD83D\uDC65', name: 'Hermes', sub: 'Integrate', running: true },
      { emoji: '\uD83D\uDD28', name: 'Hephaestus', sub: 'CI/CD' },
      { emoji: '\uD83C\uDFAF', name: 'Artemis', sub: 'E2E Tests' },
      { emoji: '\uD83D\uDEE1\uFE0F', name: 'Ares', sub: 'Audit' },
    ],
  },
  {
    title: 'Input Form \u2014 Spec Driven',
    badge: 'Guided',
    badgeStyle: { bg: '#DBEAFE', color: '#1D4ED8', border: '#93C5FD' },
    nodes: [
      { emoji: '\u26A1', name: 'Zeus', sub: 'Parse Spec', lead: true },
      { emoji: '\uD83E\uDDE0', name: 'Athena', sub: 'Plan Features', running: true },
      { emoji: '\u2600\uFE0F', name: 'Apollo', sub: 'Implement', running: true },
      { emoji: '\uD83C\uDFAF', name: 'Artemis', sub: 'Verify', running: true },
      { emoji: '\uD83D\uDEE1\uFE0F', name: 'Ares', sub: 'Compliance' },
    ],
  },
  {
    title: 'API-First Workflow',
    badge: 'Backend',
    badgeStyle: { bg: '#FFF0DC', color: '#A05A00', border: '#F0C880' },
    nodes: [
      { emoji: '\u26A1', name: 'Zeus', sub: 'Route', lead: true },
      { emoji: '\uD83E\uDDE0', name: 'Athena', sub: 'Schema Design', running: true },
      { emoji: '\u2600\uFE0F', name: 'Apollo', sub: 'Endpoints', running: true },
      { emoji: '\uD83D\uDC65', name: 'Hermes', sub: 'Integration', running: true },
      { emoji: '\uD83D\uDD25', name: 'Hades', sub: 'Load Test' },
      { emoji: '\uD83D\uDEE1\uFE0F', name: 'Ares', sub: 'Auth & Security' },
    ],
  },
  {
    title: 'Bug Fix \u2014 Hotfix Path',
    badge: 'Fast-track',
    badgeStyle: { bg: '#FEE2E2', color: '#B91C1C', border: '#FCA5A5' },
    nodes: [
      { emoji: '\u26A1', name: 'Zeus', sub: 'Triage', lead: true },
      { emoji: '\u2600\uFE0F', name: 'Apollo', sub: 'Fix', running: true },
      { emoji: '\uD83C\uDFAF', name: 'Artemis', sub: 'Regression', running: true },
      { emoji: '\uD83D\uDD28', name: 'Hephaestus', sub: 'Deploy' },
    ],
  },
]

const ROLE_LABELS: Record<RoleBadge, string> = {
  LEAD: 'Lead Agent',
  INT: 'Integration Agent',
  SPC: 'Specialist Agent',
}

function AgentDrawer({ agent, onClose }: { agent: AgentData; onClose: () => void }) {
  const [visible, setVisible] = useState(false)
  const [view, setView] = useState<'detail' | 'configure'>('detail')
  const [promptText, setPromptText] = useState(() => agent.systemPrompt || DEFAULT_PROMPTS[agent.name] || '')
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
      {/* Backdrop */}
      <div
        onClick={handleClose}
        style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.25)', zIndex: 998,
          opacity: visible ? 1 : 0, transition: 'opacity 0.25s ease',
        }}
      />

      {/* Drawer */}
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
        <div style={{
          display: 'flex', borderBottom: '1px solid #DDEC90', background: '#FFFFFF', flexShrink: 0,
        }}>
          {[
            { id: 'detail' as const, label: 'Overview' },
            { id: 'configure' as const, label: 'System Prompt' },
          ].map(tab => (
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
                    <div style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase', color: '#7A8A00', marginBottom: '4px' }}>
                      {m.label}
                    </div>
                    <div style={{ fontSize: '15px', fontWeight: 700, color: '#1A1A00' }}>{m.value}</div>
                  </div>
                ))}
              </div>

              <div style={sectionTitle}>Capabilities</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginBottom: '24px' }}>
                {agent.capabilities.map(cap => (
                  <span key={cap} style={{
                    fontSize: '12px', padding: '4px 10px', borderRadius: '20px',
                    background: '#F5F8D0', color: '#1A1A00', border: '1px solid #DDEC90', fontWeight: 600,
                  }}>
                    {cap}
                  </span>
                ))}
              </div>

              <div style={sectionTitle}>Assigned Projects</div>
              {agent.assignedProjects.length === 0 ? (
                <div style={{ fontSize: '13px', color: '#6A6A20', marginBottom: '24px', fontStyle: 'italic' }}>
                  No active project assignments
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '24px' }}>
                  {agent.assignedProjects.map(p => (
                    <div key={p} style={{
                      display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 12px',
                      background: '#FAFAF2', borderRadius: '6px', border: '1px solid #F5F8D0',
                    }}>
                      <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: '#BBCB64', flexShrink: 0 }} />
                      <span style={{ fontSize: '13px', fontWeight: 600, color: '#1A1A00' }}>{p}</span>
                    </div>
                  ))}
                </div>
              )}

              <div style={sectionTitle}>Recent Activity</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
                {agent.recentActivity.map((act, idx) => (
                  <div key={idx} style={{
                    display: 'flex', gap: '12px', padding: '10px 0',
                    borderBottom: idx < agent.recentActivity.length - 1 ? '1px solid #F5F8D0' : 'none',
                  }}>
                    <div style={{
                      width: '8px', height: '8px', borderRadius: '50%', background: '#BBCB64',
                      marginTop: '5px', flexShrink: 0,
                    }} />
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

            <div style={{
              padding: '16px 24px', borderTop: '1px solid #DDEC90', background: '#FAFAF2',
              display: 'flex', gap: '10px', flexShrink: 0,
            }}>
              <button
                style={{
                  flex: 1, fontSize: '13px', fontWeight: 700, color: '#7A8A00',
                  border: '1px solid #DDEC90', background: 'transparent',
                  borderRadius: '6px', padding: '10px 16px', cursor: 'pointer', transition: 'background 0.12s',
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#F5F8D0' }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
              >
                View Logs
              </button>
              <button
                onClick={() => setView('configure')}
                style={{
                  flex: 1, fontSize: '13px', fontWeight: 700, color: '#1A1A00',
                  background: '#BBCB64', border: 'none',
                  borderRadius: '6px', padding: '10px 16px', cursor: 'pointer', transition: 'opacity 0.12s',
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.opacity = '0.9' }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.opacity = '1' }}
              >
                Configure
              </button>
            </div>
          </>
        )}

        {/* Configure view — System Prompt Editor */}
        {view === 'configure' && (
          <>
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {/* Info banner */}
              <div style={{
                display: 'flex', alignItems: 'flex-start', gap: '10px',
                padding: '12px 14px', borderRadius: '8px',
                background: '#FAFAF2', border: '1px solid #DDEC90',
              }}>
                <span style={{ fontSize: '16px', flexShrink: 0, marginTop: '1px' }}>&#9889;</span>
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 700, color: '#1A1A00', marginBottom: '3px' }}>
                    Agent System Prompt
                  </div>
                  <div style={{ fontSize: '12px', color: '#6A6A20', lineHeight: 1.5 }}>
                    This prompt defines how <strong>{agent.name}</strong> behaves. It is prepended to every task sent to this agent.
                    Edit it to customize the agent's personality, constraints, and focus areas.
                  </div>
                </div>
              </div>

              {/* Prompt metadata */}
              <div style={{ display: 'flex', gap: '10px' }}>
                <div style={{
                  flex: 1, padding: '8px 12px', borderRadius: '6px',
                  background: '#F5F8D0', border: '1px solid #DDEC90',
                }}>
                  <div style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase', color: '#7A8A00', marginBottom: '2px' }}>
                    Model
                  </div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: '#1A1A00' }}>{agent.model}</div>
                </div>
                <div style={{
                  flex: 1, padding: '8px 12px', borderRadius: '6px',
                  background: '#F5F8D0', border: '1px solid #DDEC90',
                }}>
                  <div style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase', color: '#7A8A00', marginBottom: '2px' }}>
                    Characters
                  </div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: '#1A1A00' }}>{promptText.length.toLocaleString()}</div>
                </div>
                <div style={{
                  flex: 1, padding: '8px 12px', borderRadius: '6px',
                  background: '#F5F8D0', border: '1px solid #DDEC90',
                }}>
                  <div style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase', color: '#7A8A00', marginBottom: '2px' }}>
                    Lines
                  </div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: '#1A1A00' }}>{promptText.split('\n').length}</div>
                </div>
              </div>

              {/* Textarea */}
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
                  resize: 'none', outline: 'none',
                  transition: 'border-color 0.15s',
                }}
                onFocus={e => { e.currentTarget.style.borderColor = '#7A8A00' }}
                onBlur={e => { e.currentTarget.style.borderColor = '#DDEC90' }}
              />

              {/* Quick-insert buttons */}
              <div>
                <div style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase', color: '#7A8A00', marginBottom: '8px' }}>
                  Quick Insert
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {QUICK_INSERT_ITEMS.map(item => (
                    <button
                      key={item.label}
                      onClick={() => setPromptText(prev => prev + item.text)}
                      style={{
                        fontSize: '11px', fontWeight: 600, padding: '4px 10px', borderRadius: '20px',
                        background: 'transparent', color: '#7A8A00', border: '1px solid #DDEC90',
                        cursor: 'pointer', transition: 'background 0.12s',
                      }}
                      onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#F5F8D0' }}
                      onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Footer */}
            <div style={{
              padding: '16px 24px', borderTop: '1px solid #DDEC90', background: '#FAFAF2',
              display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0,
            }}>
              <button
                onClick={() => {
                  setPromptText(DEFAULT_PROMPTS[agent.name] || '')
                }}
                style={{
                  fontSize: '12px', fontWeight: 600, color: '#6A6A20',
                  border: '1px solid #DDEC90', background: 'transparent',
                  borderRadius: '6px', padding: '8px 14px', cursor: 'pointer', transition: 'background 0.12s',
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#F5F8D0' }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
              >
                Reset to Default
              </button>
              <div style={{ flex: 1 }} />
              <button
                onClick={() => setView('detail')}
                style={{
                  fontSize: '13px', fontWeight: 700, color: '#7A8A00',
                  border: '1px solid #DDEC90', background: 'transparent',
                  borderRadius: '6px', padding: '10px 16px', cursor: 'pointer', transition: 'background 0.12s',
                }}
                onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#F5F8D0' }}
                onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                style={{
                  fontSize: '13px', fontWeight: 700,
                  color: saved ? '#FFFFFF' : '#1A1A00',
                  background: saved ? '#7A8A00' : '#BBCB64',
                  border: 'none',
                  borderRadius: '6px', padding: '10px 20px', cursor: 'pointer',
                  transition: 'all 0.2s',
                }}
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

export function AgentsView() {
  const [hoveredCard, setHoveredCard] = useState<string | null>(null)
  const [selectedAgent, setSelectedAgent] = useState<AgentData | null>(null)

  return (
    <div style={{ fontFamily: "'Inter', sans-serif" }}>
      {/* Page Header */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: '20px' }}>
        <div>
          <div style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '2px', textTransform: 'uppercase', color: '#7A8A00', marginBottom: '3px' }}>
            Multi-Agent System
          </div>
          <h1 style={{ fontSize: '31px', fontWeight: 700, color: '#1A1A00', margin: 0, lineHeight: 1.2 }}>
            Agent <span style={{ color: '#7A8A00' }}>Roster</span>
          </h1>
          <p style={{ fontSize: '14px', color: '#6A6A20', marginTop: '3px' }}>
            16 agents deployed &middot; 14 active &middot; 2 idle &middot; Real-time orchestration
          </p>
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            style={{
              fontSize: '13px', fontWeight: 700, color: '#7A8A00',
              border: '1px solid #DDEC90', background: 'transparent',
              borderRadius: '4px', padding: '8px 16px', cursor: 'pointer',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.background = '#F5F8D0' }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
          >
            &darr; Agent Report
          </button>
          <button
            style={{
              fontSize: '13px', fontWeight: 700, color: '#1A1A00',
              background: '#BBCB64', border: 'none',
              borderRadius: '4px', padding: '8px 16px', cursor: 'pointer',
            }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.opacity = '0.9' }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.opacity = '1' }}
          >
            + Configure Agent
          </button>
        </div>
      </div>

      {/* Agent Cards Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '14px', marginBottom: '24px' }}>
        {AGENTS.map((agent) => {
          const roleStyle = ROLE_STYLES[agent.role]
          const isIdle = agent.status === 'idle'
          return (
            <div
              key={agent.name}
              style={{
                background: '#FFFFFF',
                border: '1px solid #DDEC90',
                borderRadius: '8px',
                padding: '16px',
                opacity: isIdle ? 0.75 : 1,
                transform: hoveredCard === agent.name ? 'translateY(-2px)' : 'none',
                boxShadow: hoveredCard === agent.name ? '0 4px 12px rgba(187,203,100,0.15)' : 'none',
                borderColor: hoveredCard === agent.name ? '#BBCB64' : '#DDEC90',
                transition: 'all 0.15s',
                cursor: 'pointer',
              }}
              onClick={() => setSelectedAgent(agent)}
              onMouseEnter={() => setHoveredCard(agent.name)}
              onMouseLeave={() => setHoveredCard(null)}
            >
              <div style={{ fontSize: '28px', marginBottom: '10px' }}>{agent.emoji}</div>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '6px' }}>
                <span style={{ fontSize: '19px', fontWeight: 700, color: '#1A1A00' }}>{agent.name}</span>
                <span style={{
                  fontSize: '10px', fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase',
                  borderRadius: '20px', padding: '2px 7px',
                  background: roleStyle.bg, color: roleStyle.color, border: `1px solid ${roleStyle.border}`,
                }}>
                  {agent.role}
                </span>
              </div>
              <div style={{ fontSize: '14px', color: '#6A6A20', marginBottom: '10px' }}>{agent.subtitle}</div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', color: isIdle ? '#6A6A20' : '#BBCB64' }}>
                  <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: isIdle ? '#E0E0E0' : '#BBCB64', display: 'inline-block' }} />
                  {isIdle ? 'Idle' : 'Working'}
                </div>
                <span style={{ fontSize: '13px', color: '#6A6A20' }}>{agent.tasks} active task{agent.tasks !== 1 ? 's' : ''}</span>
              </div>
              <div style={{ height: '1px', background: '#F5F8D0', margin: '10px 0' }} />
              <div style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase', color: '#7A8A00', marginBottom: '6px' }}>
                Capabilities
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px' }}>
                {agent.capabilities.map((cap) => (
                  <span key={cap} style={{
                    fontSize: '10px', padding: '2px 7px', borderRadius: '10px',
                    background: '#F5F8D0', color: '#1A1A00', border: '1px solid #DDEC90',
                  }}>
                    {cap}
                  </span>
                ))}
              </div>
            </div>
          )
        })}
      </div>

      {/* Orchestration Pathways */}
      <div style={{ marginTop: '28px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px' }}>
          <div>
            <div style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '2px', textTransform: 'uppercase', color: '#7A8A00', marginBottom: '2px' }}>
              Orchestration Pathways
            </div>
            <p style={{ fontSize: '13px', color: '#6A6A20', margin: 0 }}>
              Agent routing flows for different project types
            </p>
          </div>
          <span style={{
            fontSize: '11px', fontWeight: 700, padding: '4px 12px', borderRadius: '20px',
            background: '#F5F8D0', color: '#7A8A00', border: '1px solid #DDEC90',
          }}>
            {ORCH_FLOWS.length} flows
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '14px' }}>
          {ORCH_FLOWS.map((flow) => (
            <div
              key={flow.title}
              style={{
                background: '#FFFFFF',
                border: '1px solid #DDEC90',
                borderRadius: '10px',
                overflow: 'hidden',
                transition: 'box-shadow 0.15s, border-color 0.15s',
              }}
              onMouseEnter={e => {
                (e.currentTarget as HTMLElement).style.boxShadow = '0 4px 16px rgba(187,203,100,0.18)'
                ;(e.currentTarget as HTMLElement).style.borderColor = '#BBCB64'
              }}
              onMouseLeave={e => {
                (e.currentTarget as HTMLElement).style.boxShadow = 'none'
                ;(e.currentTarget as HTMLElement).style.borderColor = '#DDEC90'
              }}
            >
              {/* Flow header */}
              <div style={{
                padding: '12px 16px',
                borderBottom: '1px solid #F5F8D0',
                background: '#FAFAF2',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}>
                <span style={{ fontSize: '13px', fontWeight: 700, color: '#1A1A00' }}>
                  {flow.title}
                </span>
                <span style={{
                  fontSize: '10px', fontWeight: 700, padding: '3px 10px', borderRadius: '20px',
                  background: flow.badgeStyle.bg, color: flow.badgeStyle.color,
                  border: `1px solid ${flow.badgeStyle.border}`,
                }}>
                  {flow.badge}
                </span>
              </div>

              {/* Flow nodes */}
              <div style={{ padding: '18px 16px 14px', overflowX: 'auto' }}>
                <div style={{ display: 'flex', alignItems: 'flex-start' }}>
                  {flow.nodes.map((node, idx) => (
                    <React.Fragment key={`${flow.title}-${node.name}`}>
                      <div style={{
                        display: 'flex', flexDirection: 'column', alignItems: 'center',
                        minWidth: '64px', position: 'relative',
                      }}>
                        {/* Node circle */}
                        <div style={{
                          width: '44px', height: '44px', borderRadius: '12px',
                          background: node.lead ? '#FFF8EE' : node.running ? '#FAFFF0' : '#FAFAF2',
                          border: `2px solid ${node.lead ? '#F79A19' : node.running ? '#BBCB64' : '#E5E7EB'}`,
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: '20px', position: 'relative',
                          boxShadow: (node.running || node.lead)
                            ? `0 0 0 3px ${node.lead ? 'rgba(247,154,25,0.15)' : 'rgba(187,203,100,0.15)'}`
                            : 'none',
                          transition: 'transform 0.15s',
                        }}>
                          {node.emoji}
                          {(node.running || node.lead) && (
                            <span style={{
                              position: 'absolute', top: '-2px', right: '-2px',
                              width: '10px', height: '10px', borderRadius: '50%',
                              background: node.lead ? '#F79A19' : '#BBCB64',
                              border: '2px solid #FFFFFF',
                              boxShadow: `0 0 4px ${node.lead ? 'rgba(247,154,25,0.4)' : 'rgba(187,203,100,0.4)'}`,
                            }} />
                          )}
                        </div>
                        {/* Labels */}
                        <span style={{
                          fontSize: '11px', fontWeight: 700, color: '#1A1A00',
                          textAlign: 'center', marginTop: '6px', lineHeight: 1.2,
                        }}>
                          {node.name}
                        </span>
                        <span style={{
                          fontSize: '10px', color: '#6A6A20', textAlign: 'center',
                          marginTop: '1px', lineHeight: 1.2,
                        }}>
                          {node.sub}
                        </span>
                      </div>
                      {/* Connector arrow */}
                      {idx < flow.nodes.length - 1 && (
                        <div style={{
                          display: 'flex', alignItems: 'center',
                          marginTop: '18px', minWidth: '20px', flex: 1,
                        }}>
                          <div style={{
                            flex: 1, height: '2px', minWidth: '8px',
                            background: (node.running || node.lead)
                              ? 'linear-gradient(90deg, #BBCB64, #DDEC90)'
                              : '#E5E7EB',
                          }} />
                          <svg width="8" height="10" viewBox="0 0 8 10" style={{ flexShrink: 0, marginLeft: '-1px' }}>
                            <path
                              d="M0 0 L8 5 L0 10 Z"
                              fill={(node.running || node.lead) ? '#BBCB64' : '#E5E7EB'}
                            />
                          </svg>
                        </div>
                      )}
                    </React.Fragment>
                  ))}
                </div>
              </div>

              {/* Flow footer */}
              <div style={{
                padding: '8px 16px',
                borderTop: '1px solid #F5F8D0',
                background: '#FEFFF8',
                display: 'flex', alignItems: 'center', gap: '12px',
              }}>
                <span style={{ fontSize: '10px', color: '#9A9A60' }}>
                  {flow.nodes.length} agents
                </span>
                <span style={{ fontSize: '10px', color: '#DDEC90' }}>&bull;</span>
                <span style={{ fontSize: '10px', color: '#9A9A60' }}>
                  {flow.nodes.filter(n => n.running || n.lead).length} active
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Agent Detail Drawer */}
      {selectedAgent && (
        <AgentDrawer agent={selectedAgent} onClose={() => setSelectedAgent(null)} />
      )}
    </div>
  )
}
