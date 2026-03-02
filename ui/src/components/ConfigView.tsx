import { useState } from 'react'

// ---------------------------------------------------------------------------
// Toggle component
// ---------------------------------------------------------------------------

function Toggle({ on, onToggle }: { on: boolean; onToggle: () => void }) {
  return (
    <button
      onClick={onToggle}
      style={{
        width: '38px', height: '20px',
        background: on ? '#BBCB64' : '#DDEC90',
        borderRadius: '10px', position: 'relative', cursor: 'pointer',
        border: 'none', flexShrink: 0, transition: 'background 0.15s',
      }}
    >
      <span style={{
        position: 'absolute', top: '3px', left: on ? '21px' : '3px',
        width: '14px', height: '14px', borderRadius: '50%', background: '#FFFFFF',
        transition: 'left 0.15s',
      }} />
    </button>
  )
}

// ---------------------------------------------------------------------------
// Shared styles
// ---------------------------------------------------------------------------

const fieldLabelStyle: React.CSSProperties = {
  fontSize: '12px', fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase', color: '#6A6A20', marginBottom: '5px',
}
const fieldSubStyle: React.CSSProperties = {
  fontSize: '13px', color: '#6A6A20', marginBottom: '5px',
}
const selectStyle: React.CSSProperties = {
  width: '100%', fontSize: '16px', padding: '8px 10px', borderRadius: '6px',
  border: '1px solid #DDEC90', background: '#FAFAF2', color: '#1A1A00',
  outline: 'none', cursor: 'pointer',
}

// ---------------------------------------------------------------------------
// Toggle row helper
// ---------------------------------------------------------------------------

interface ToggleRowProps {
  name: string
  desc: string
  on: boolean
  onToggle: () => void
  isLast?: boolean
}

function ToggleRow({ name, desc, on, onToggle, isLast }: ToggleRowProps) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '10px 0', borderBottom: isLast ? 'none' : '1px solid #F5F8D0',
    }}>
      <div>
        <div style={{ fontSize: '16px', fontWeight: 700, color: '#1A1A00' }}>{name}</div>
        <div style={{ fontSize: '13px', color: '#6A6A20', marginTop: '2px' }}>{desc}</div>
      </div>
      <Toggle on={on} onToggle={onToggle} />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Select field helper
// ---------------------------------------------------------------------------

interface SelectFieldProps {
  label: string
  sub?: string
  options: string[]
  value: string
  onChange: (val: string) => void
}

function SelectField({ label, sub, options, value, onChange }: SelectFieldProps) {
  return (
    <div>
      <div style={fieldLabelStyle}>{label}</div>
      {sub && <div style={fieldSubStyle}>{sub}</div>}
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={selectStyle}
        onFocus={(e) => { (e.currentTarget as HTMLElement).style.borderColor = '#BBCB64' }}
        onBlur={(e) => { (e.currentTarget as HTMLElement).style.borderColor = '#DDEC90' }}
      >
        {options.map((opt) => (
          <option key={opt} value={opt}>{opt}</option>
        ))}
      </select>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Tab definitions
// ---------------------------------------------------------------------------

interface ConfigTab {
  id: string
  label: string
  icon: string
}

const CONFIG_TABS: ConfigTab[] = [
  { id: 'models', label: 'Models', icon: '⚙' },
  { id: 'framework', label: 'Framework', icon: '◈' },
  { id: 'hitl', label: 'HITL', icon: '⊘' },
  { id: 'budget', label: 'Budget', icon: '◉' },
  { id: 'connectors', label: 'Connectors', icon: '⬡' },
]

// ---------------------------------------------------------------------------
// Connector card
// ---------------------------------------------------------------------------

interface ConnectorDef {
  id: string
  name: string
  description: string
  icon: string
  color: string
  connected: boolean
  category: 'design' | 'communication' | 'devops' | 'storage'
}

const CONNECTORS: ConnectorDef[] = [
  { id: 'figma', name: 'Figma', description: 'Import designs, components, and design tokens directly from Figma files', icon: '✦', color: '#A259FF', connected: false, category: 'design' },
  { id: 'slack', name: 'Slack', description: 'Send notifications, HITL prompts, and agent updates to Slack channels', icon: '⊞', color: '#E01E5A', connected: true, category: 'communication' },
  { id: 'github', name: 'GitHub', description: 'Auto-create PRs, manage issues, and sync repository activity', icon: '⊛', color: '#24292F', connected: true, category: 'devops' },
  { id: 'linear', name: 'Linear', description: 'Sync features with Linear issues and track sprint progress', icon: '◇', color: '#5E6AD2', connected: false, category: 'devops' },
  { id: 'notion', name: 'Notion', description: 'Pull requirements from Notion docs and sync project documentation', icon: '▣', color: '#000000', connected: false, category: 'storage' },
  { id: 'discord', name: 'Discord', description: 'Real-time agent updates and team notifications via Discord webhooks', icon: '⬡', color: '#5865F2', connected: false, category: 'communication' },
  { id: 'vercel', name: 'Vercel', description: 'Auto-deploy preview builds and manage production deployments', icon: '▲', color: '#000000', connected: false, category: 'devops' },
  { id: 'supabase', name: 'Supabase', description: 'Provision databases, manage migrations, and sync schema changes', icon: '⬢', color: '#3ECF8E', connected: false, category: 'storage' },
  { id: 'jira', name: 'Jira', description: 'Bi-directional sync between features and Jira tickets', icon: '◆', color: '#0052CC', connected: false, category: 'devops' },
  { id: 'sentry', name: 'Sentry', description: 'Auto-create features from error reports and track resolution', icon: '◎', color: '#362D59', connected: false, category: 'devops' },
]


function ConnectorCard({ connector, onToggle }: { connector: ConnectorDef; onToggle: () => void }) {
  const [hovered, setHovered] = useState(false)

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        background: '#FFFFFF',
        border: connector.connected ? '1px solid #BBCB64' : '1px solid #DDEC90',
        borderRadius: '10px',
        padding: '18px',
        display: 'flex', flexDirection: 'column', gap: '12px',
        transition: 'all 0.15s',
        boxShadow: hovered ? '0 2px 12px rgba(0,0,0,0.06)' : 'none',
        transform: hovered ? 'translateY(-1px)' : 'none',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div style={{
          width: '40px', height: '40px', borderRadius: '10px',
          background: connector.connected ? `${connector.color}18` : '#FAFAF2',
          border: `1px solid ${connector.connected ? connector.color + '40' : '#DDEC90'}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: '18px', color: connector.color, flexShrink: 0,
        }}>
          {connector.icon}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: '16px', fontWeight: 700, color: '#1A1A00' }}>{connector.name}</div>
        </div>
        {connector.connected && (
          <span style={{
            fontSize: '10px', fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase',
            background: '#F5F8D0', color: '#7A8A00', border: '1px solid #DDEC90',
            borderRadius: '20px', padding: '3px 10px', flexShrink: 0,
          }}>
            Connected
          </span>
        )}
      </div>

      <div style={{ fontSize: '13px', color: '#6A6A20', lineHeight: 1.5 }}>
        {connector.description}
      </div>

      <button
        onClick={onToggle}
        style={{
          fontSize: '13px', fontWeight: 700,
          color: connector.connected ? '#7A8A00' : '#1A1A00',
          background: connector.connected ? 'transparent' : '#BBCB64',
          border: connector.connected ? '1px solid #DDEC90' : 'none',
          borderRadius: '6px', padding: '8px 14px',
          cursor: 'pointer', transition: 'all 0.12s',
          alignSelf: 'flex-start',
        }}
        onMouseEnter={(e) => {
          if (connector.connected) (e.currentTarget as HTMLElement).style.background = '#FFF0DC'
          else (e.currentTarget as HTMLElement).style.opacity = '0.9'
        }}
        onMouseLeave={(e) => {
          if (connector.connected) (e.currentTarget as HTMLElement).style.background = 'transparent'
          else (e.currentTarget as HTMLElement).style.opacity = '1'
        }}
      >
        {connector.connected ? 'Disconnect' : 'Connect'}
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ConfigView
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Segmented control
// ---------------------------------------------------------------------------

interface SegmentedControlProps {
  label: string
  sub?: string
  options: string[]
  value: string
  onChange: (val: string) => void
}

function SegmentedControl({ label, sub, options, value, onChange }: SegmentedControlProps) {
  return (
    <div>
      <div style={fieldLabelStyle}>{label}</div>
      {sub && <div style={fieldSubStyle}>{sub}</div>}
      <div style={{
        display: 'flex', borderRadius: '6px', overflow: 'hidden',
        border: '1px solid #DDEC90',
      }}>
        {options.map((opt) => (
          <button
            key={opt}
            onClick={() => onChange(opt)}
            style={{
              flex: 1, padding: '9px 0', fontSize: '15px', fontWeight: 700,
              cursor: 'pointer', border: 'none',
              borderRight: '1px solid #DDEC90',
              background: value === opt ? '#BBCB64' : '#FAFAF2',
              color: value === opt ? '#1A1A00' : '#6A6A20',
              transition: 'all 0.12s',
            }}
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// ConfigView types
// ---------------------------------------------------------------------------

interface ToggleState {
  schemaMigration: boolean
  architectureChanges: boolean
  downtimeOps: boolean
  autoApproveFormatting: boolean
  autoSwitchHaiku: boolean
  weeklyReports: boolean
  yoloMode: boolean
  headlessBrowser: boolean
}

const DEFAULT_TOGGLES: ToggleState = {
  schemaMigration: true,
  architectureChanges: true,
  downtimeOps: true,
  autoApproveFormatting: false,
  autoSwitchHaiku: true,
  weeklyReports: true,
  yoloMode: false,
  headlessBrowser: true,
}

export function ConfigView() {
  const [activeTab, setActiveTab] = useState('models')
  const [toggles, setToggles] = useState<ToggleState>(DEFAULT_TOGGLES)
  const [connectors, setConnectors] = useState(CONNECTORS)

  const [primaryModel, setPrimaryModel] = useState('Claude Opus 4.6')
  const [secondaryModel, setSecondaryModel] = useState('Claude Haiku 4.5')
  const [maxTokens, setMaxTokens] = useState('200K')
  const [framework, setFramework] = useState('React + TypeScript (Vite)')
  const [stateManagement, setStateManagement] = useState('Zustand (recommended)')
  const [archPattern, setArchPattern] = useState('Feature-based monorepo')
  const [hitlMode, setHitlMode] = useState('Standard')
  const [budgetCap, setBudgetCap] = useState('$5,000')
  const [alertThreshold, setAlertThreshold] = useState('80%')
  const [connectorFilter, setConnectorFilter] = useState('all')
  const [regressionAgents, setRegressionAgents] = useState('1')
  const [featuresPerAgent, setFeaturesPerAgent] = useState('3')

  const toggle = (key: keyof ToggleState) => {
    setToggles((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const toggleConnector = (id: string) => {
    setConnectors((prev) =>
      prev.map((c) => c.id === id ? { ...c, connected: !c.connected } : c)
    )
  }

  const filteredConnectors = connectorFilter === 'all'
    ? connectors
    : connectorFilter === 'connected'
      ? connectors.filter((c) => c.connected)
      : connectors.filter((c) => c.category === connectorFilter)

  const connectedCount = connectors.filter((c) => c.connected).length

  const panelStyle: React.CSSProperties = {
    background: '#FFFFFF', border: '1px solid #DDEC90', borderRadius: '10px',
    padding: '24px', display: 'flex', flexDirection: 'column', gap: '18px',
  }

  return (
    <div style={{ fontFamily: "'Inter', sans-serif" }}>
      {/* Page Header */}
      <div style={{ marginBottom: '20px' }}>
        <div style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '2px', textTransform: 'uppercase', color: '#7A8A00', marginBottom: '3px' }}>
          Platform Control
        </div>
        <h1 style={{ fontSize: '31px', fontWeight: 700, color: '#1A1A00', margin: 0, lineHeight: 1.2 }}>
          Configuration & <span style={{ color: '#7A8A00' }}>Governance</span>
        </h1>
      </div>

      {/* Tab bar */}
      <div style={{
        display: 'flex', gap: '2px', marginBottom: '20px',
        borderBottom: '2px solid #DDEC90', paddingBottom: '0',
      }}>
        {CONFIG_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              fontSize: '14px', fontWeight: 700, letterSpacing: '0.5px',
              textTransform: 'uppercase',
              padding: '10px 20px',
              cursor: 'pointer', border: 'none',
              borderBottom: activeTab === tab.id ? '2px solid #BBCB64' : '2px solid transparent',
              marginBottom: '-2px',
              background: activeTab === tab.id ? '#F5F8D0' : 'transparent',
              color: activeTab === tab.id ? '#1A1A00' : '#6A6A20',
              borderRadius: '6px 6px 0 0',
              transition: 'all 0.12s',
              display: 'flex', alignItems: 'center', gap: '6px',
            }}
            onMouseEnter={(e) => {
              if (activeTab !== tab.id) (e.currentTarget as HTMLElement).style.color = '#1A1A00'
            }}
            onMouseLeave={(e) => {
              if (activeTab !== tab.id) (e.currentTarget as HTMLElement).style.color = '#6A6A20'
            }}
          >
            <span style={{ fontSize: '15px' }}>{tab.icon}</span>
            {tab.label}
            {tab.id === 'connectors' && connectedCount > 0 && (
              <span style={{
                fontSize: '11px', fontWeight: 700,
                background: '#BBCB64', color: '#1A1A00',
                borderRadius: '10px', padding: '1px 7px', marginLeft: '2px',
              }}>
                {connectedCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'models' && (
        <div style={panelStyle}>
          <div style={{ fontSize: '13px', color: '#6A6A20', marginBottom: '4px' }}>
            Configure which AI models power your agents for different task types.
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '18px' }}>
            <SelectField
              label="Primary Model"
              sub="Used for complex reasoning, architecture decisions, and code generation"
              options={['Claude Opus 4.6', 'Claude Sonnet 4.5', 'Claude Sonnet 4.0', 'GPT-4o']}
              value={primaryModel}
              onChange={setPrimaryModel}
            />
            <SelectField
              label="Secondary Model"
              sub="Used for routine tasks, formatting, and simple queries"
              options={['Claude Haiku 4.5', 'Claude Haiku 3.5', 'Claude Sonnet 4.5', 'GPT-4o Mini']}
              value={secondaryModel}
              onChange={setSecondaryModel}
            />
          </div>
          <SelectField
            label="Max Tokens per Task"
            options={['100K', '150K', '200K', '250K']}
            value={maxTokens}
            onChange={setMaxTokens}
          />

          {/* Divider */}
          <div style={{ height: '1px', background: '#DDEC90' }} />

          <ToggleRow
            name="YOLO Mode"
            desc="Skip testing for rapid prototyping"
            on={toggles.yoloMode}
            onToggle={() => toggle('yoloMode')}
          />
          <ToggleRow
            name="Headless Browser"
            desc="Run browser without visible window (saves CPU)"
            on={toggles.headlessBrowser}
            onToggle={() => toggle('headlessBrowser')}
            isLast
          />

          <SegmentedControl
            label="Regression Agents"
            sub="Number of regression testing agents (0 = disabled)"
            options={['0', '1', '2', '3']}
            value={regressionAgents}
            onChange={setRegressionAgents}
          />
          <SegmentedControl
            label="Features per Agent"
            sub="Number of features assigned to each coding agent"
            options={['1', '2', '3']}
            value={featuresPerAgent}
            onChange={setFeaturesPerAgent}
          />
        </div>
      )}

      {activeTab === 'framework' && (
        <div style={panelStyle}>
          <div style={{ fontSize: '13px', color: '#6A6A20', marginBottom: '4px' }}>
            Set default output frameworks and architectural patterns for generated code.
          </div>
          <SelectField
            label="Default Output Framework"
            options={['React + TypeScript (Vite)', 'Next.js', 'Vue 3', 'Angular']}
            value={framework}
            onChange={setFramework}
          />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '18px' }}>
            <SelectField
              label="State Management"
              options={['Zustand (recommended)', 'Redux Toolkit', 'Jotai', 'Context API']}
              value={stateManagement}
              onChange={setStateManagement}
            />
            <SelectField
              label="Architectural Pattern"
              options={['Feature-based monorepo', 'Micro-frontends', 'Layered']}
              value={archPattern}
              onChange={setArchPattern}
            />
          </div>
        </div>
      )}

      {activeTab === 'hitl' && (
        <div style={panelStyle}>
          <div style={{ fontSize: '13px', color: '#6A6A20', marginBottom: '4px' }}>
            Control when agents pause for human review and approval.
          </div>
          <SelectField
            label="HITL Trigger Mode"
            options={['Standard', 'Verbose', 'Minimal']}
            value={hitlMode}
            onChange={setHitlMode}
          />
          <div>
            <ToggleRow
              name="Schema migration approvals"
              desc="Require human approval before any DB schema changes"
              on={toggles.schemaMigration}
              onToggle={() => toggle('schemaMigration')}
            />
            <ToggleRow
              name="Architecture pattern changes"
              desc="Escalate if agent recommends structural changes"
              on={toggles.architectureChanges}
              onToggle={() => toggle('architectureChanges')}
            />
            <ToggleRow
              name="Downtime-requiring operations"
              desc="Always require approval when downtime is predicted"
              on={toggles.downtimeOps}
              onToggle={() => toggle('downtimeOps')}
            />
            <ToggleRow
              name="Auto-approve formatting tasks"
              desc="Bypass HITL for linting, formatting, and docs"
              on={toggles.autoApproveFormatting}
              onToggle={() => toggle('autoApproveFormatting')}
              isLast
            />
          </div>
        </div>
      )}

      {activeTab === 'budget' && (
        <div style={panelStyle}>
          <div style={{ fontSize: '13px', color: '#6A6A20', marginBottom: '4px' }}>
            Set spending limits and cost optimization rules across all agents.
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '18px' }}>
            <SelectField
              label="Monthly Budget Cap"
              options={['$5,000', '$7,500', '$10,000', 'Custom']}
              value={budgetCap}
              onChange={setBudgetCap}
            />
            <SelectField
              label="Budget Alert Threshold"
              options={['80%', '90%', '100%']}
              value={alertThreshold}
              onChange={setAlertThreshold}
            />
          </div>
          <div>
            <ToggleRow
              name="Auto-switch to Haiku on budget alert"
              desc="Use cheaper model for routine tasks when near budget"
              on={toggles.autoSwitchHaiku}
              onToggle={() => toggle('autoSwitchHaiku')}
            />
            <ToggleRow
              name="Weekly cost reports via email"
              desc="Send governance reports to admins every Monday"
              on={toggles.weeklyReports}
              onToggle={() => toggle('weeklyReports')}
              isLast
            />
          </div>
        </div>
      )}

      {activeTab === 'connectors' && (
        <div style={panelStyle}>
          {/* Connector header row */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <div style={{ fontSize: '13px', color: '#6A6A20' }}>
              {connectedCount} of {connectors.length} integrations active
            </div>
            {/* Category filter pills */}
            <div style={{ display: 'flex', gap: '4px' }}>
              {[
                { id: 'all', label: 'All' },
                { id: 'connected', label: 'Connected' },
                { id: 'design', label: 'Design' },
                { id: 'communication', label: 'Comms' },
                { id: 'devops', label: 'DevOps' },
                { id: 'storage', label: 'Data' },
              ].map((f) => (
                <button
                  key={f.id}
                  onClick={() => setConnectorFilter(f.id)}
                  style={{
                    fontSize: '12px', fontWeight: 700,
                    borderRadius: '20px', padding: '4px 12px',
                    cursor: 'pointer', transition: 'all 0.12s',
                    border: connectorFilter === f.id ? '1px solid #BBCB64' : '1px solid #DDEC90',
                    background: connectorFilter === f.id ? '#BBCB64' : 'transparent',
                    color: connectorFilter === f.id ? '#1A1A00' : '#6A6A20',
                  }}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {/* Connector grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px' }}>
            {filteredConnectors.map((connector) => (
              <ConnectorCard
                key={connector.id}
                connector={connector}
                onToggle={() => toggleConnector(connector.id)}
              />
            ))}
          </div>

          {filteredConnectors.length === 0 && (
            <div style={{
              textAlign: 'center', padding: '40px', color: '#6A6A20',
              background: '#FAFAF2', borderRadius: '10px', border: '1px solid #DDEC90',
            }}>
              No connectors match this filter.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
