import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useProjects, useDeleteProject } from '../hooks/useProjects'
import { NewProjectModal } from '../components/NewProjectModal'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { DashboardSidebar } from '../components/DashboardSidebar'
import { DashboardHeader } from '../components/DashboardHeader'
import { StatsCardRow } from '../components/StatsCardRow'
import { ProjectTable } from '../components/ProjectTable'
import { AgentRoster } from '../components/AgentRoster'
import { TokenUsagePanel } from '../components/TokenUsagePanel'
import { LiveOrchestration } from '../components/LiveOrchestration'
import { AgentsView } from '../components/AgentsView'
import { AnalyticsView } from '../components/AnalyticsView'
import { ConfigView } from '../components/ConfigView'

export function HomePage() {
  const { data: projects, isLoading } = useProjects()
  const [showNewProject, setShowNewProject] = useState(false)
  const [projectToDelete, setProjectToDelete] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState('DASHBOARD')
  const deleteProject = useDeleteProject()
  const navigate = useNavigate()

  // Phase filter state
  const [activePhase, setActivePhase] = useState('All')
  // Input type filter state
  const [activeInputType, setActiveInputType] = useState('All')
  // Search state
  const [searchQuery, setSearchQuery] = useState('')

  const projectList = projects ?? []
  const totalFeatures = projectList.reduce((sum, p) => sum + p.stats.total, 0)
  const completedFeatures = projectList.reduce((sum, p) => sum + p.stats.passing, 0)

  const handleProjectCreated = (projectName: string) => {
    navigate(`/odyssey/${encodeURIComponent(projectName)}`)
  }

  const handleOpenProject = (name: string) => {
    navigate(`/odyssey/${encodeURIComponent(name)}`)
  }

  const handleConfirmDelete = async () => {
    if (!projectToDelete) return
    try {
      await deleteProject.mutateAsync(projectToDelete)
      setProjectToDelete(null)
    } catch (error) {
      console.error('Failed to delete project:', error)
      setProjectToDelete(null)
    }
  }

  const firstProject = projectList[0]

  const now = new Date()
  const dateStr = now.toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'short', day: 'numeric' })

  const phases = ['All', 'Discovery', 'Build', 'Review', 'Deploy']
  const inputTypes = ['All', 'Folder', 'Figma', 'Prototype']

  return (
    <div className="flex flex-col min-h-screen" style={{ background: '#FAFAF2' }}>
      <DashboardHeader
        projectCount={projectList.length}
        onNewProject={() => setShowNewProject(true)}
        activeTab={activeTab}
        onTabChange={setActiveTab}
      />

      <div className="flex flex-1 min-h-0">
        <DashboardSidebar
          projects={projectList}
          onNewProject={() => setShowNewProject(true)}
          onTabChange={setActiveTab}
        />

        <div className="flex-1 flex flex-col min-w-0">

        <main className="flex-1 p-6 overflow-y-auto" style={{ fontFamily: "'Inter', sans-serif" }}>
          {activeTab === 'AGENTS' && <AgentsView />}
          {activeTab === 'ANALYTICS' && <AnalyticsView projectCount={projectList.length} />}
          {activeTab === 'CONFIG' && <ConfigView />}
          {activeTab === 'DASHBOARD' && (
            <>
              {/* Command Center Title + Actions */}
              <div className="flex items-start justify-between mb-5">
                <div>
                  <div style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '2px', textTransform: 'uppercase', color: '#7A8A00', marginBottom: '4px' }}>
                    Command Center
                  </div>
                  <h1 style={{ fontSize: '31px', fontWeight: 700, color: '#1A1A00', margin: 0, lineHeight: 1.2 }}>
                    Project <span style={{ color: '#7A8A00' }}>Overview</span>
                  </h1>
                  <p style={{ fontSize: '14px', color: '#6A6A20', marginTop: '4px' }}>
                    Multi-agent orchestration across {projectList.length} active workstreams &middot; {dateStr}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    style={{
                      fontSize: '13px',
                      fontWeight: 700,
                      color: '#7A8A00',
                      border: '1px solid #DDEC90',
                      background: 'transparent',
                      borderRadius: '4px',
                      padding: '6px 12px',
                      cursor: 'pointer',
                      transition: 'background 0.12s',
                    }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.background = '#F5F8D0' }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.background = 'transparent' }}
                  >
                    &darr; Export Report
                  </button>
                  <button
                    onClick={() => setShowNewProject(true)}
                    style={{
                      fontSize: '13px',
                      fontWeight: 700,
                      color: '#1A1A00',
                      background: '#BBCB64',
                      border: 'none',
                      borderRadius: '4px',
                      padding: '6px 14px',
                      cursor: 'pointer',
                      transition: 'opacity 0.12s',
                    }}
                    onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.opacity = '0.9' }}
                    onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.opacity = '1' }}
                  >
                    + New Project
                  </button>
                </div>
              </div>

              {/* Filter Bar */}
              <div
                style={{
                  background: '#FFFFFF',
                  border: '1px solid #DDEC90',
                  borderRadius: '8px',
                  padding: '10px 14px',
                  marginBottom: '18px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '14px',
                }}
              >
                {/* Phase group */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase', color: '#7A8A00', marginRight: '4px' }}>
                    Phase
                  </span>
                  {phases.map((pill) => (
                    <button
                      key={pill}
                      onClick={() => setActivePhase(pill)}
                      style={{
                        fontSize: '13px',
                        fontWeight: 700,
                        borderRadius: '20px',
                        border: activePhase === pill ? '1px solid #BBCB64' : '1px solid #DDEC90',
                        background: activePhase === pill ? '#BBCB64' : 'transparent',
                        color: activePhase === pill ? '#1A1A00' : '#6A6A20',
                        padding: '3px 10px',
                        cursor: 'pointer',
                        transition: 'all 0.12s',
                      }}
                    >
                      {pill}
                    </button>
                  ))}
                </div>

                {/* Vertical divider */}
                <div style={{ width: '1px', height: '20px', background: '#DDEC90' }} />

                {/* Input type group */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 700, letterSpacing: '1px', textTransform: 'uppercase', color: '#7A8A00', marginRight: '4px' }}>
                    Input
                  </span>
                  {inputTypes.map((pill) => (
                    <button
                      key={pill}
                      onClick={() => setActiveInputType(pill)}
                      style={{
                        fontSize: '13px',
                        fontWeight: 700,
                        borderRadius: '20px',
                        border: activeInputType === pill ? '1px solid #BBCB64' : '1px solid #DDEC90',
                        background: activeInputType === pill ? '#BBCB64' : 'transparent',
                        color: activeInputType === pill ? '#1A1A00' : '#6A6A20',
                        padding: '3px 10px',
                        cursor: 'pointer',
                        transition: 'all 0.12s',
                      }}
                    >
                      {pill}
                    </button>
                  ))}
                </div>

                {/* Spacer */}
                <div style={{ flex: 1 }} />

                {/* Search */}
                <input
                  type="text"
                  placeholder="Search projects..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{
                    fontSize: '14px',
                    borderRadius: '6px',
                    border: '1px solid #DDEC90',
                    background: '#FAFAF2',
                    padding: '5px 10px',
                    width: '160px',
                    outline: 'none',
                    color: '#1A1A00',
                    transition: 'border-color 0.12s',
                  }}
                  onFocus={(e) => { (e.currentTarget as HTMLElement).style.borderColor = '#BBCB64' }}
                  onBlur={(e) => { (e.currentTarget as HTMLElement).style.borderColor = '#DDEC90' }}
                />
              </div>

              {/* Stats Row */}
              {isLoading ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: '12px', marginBottom: '18px' }}>
                  {[1, 2, 3, 4, 5].map(i => (
                    <div key={i} style={{ height: '80px', borderRadius: '8px', background: '#F5F8D0', opacity: 0.4 }} />
                  ))}
                </div>
              ) : (
                <div style={{ marginBottom: '18px' }}>
                  <StatsCardRow
                    projectCount={projectList.length}
                    totalFeatures={totalFeatures}
                    completedFeatures={completedFeatures}
                  />
                </div>
              )}

              {/* Two-Column: Table + Roster */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: '18px', marginBottom: '18px' }}>
                <div>
                  {isLoading ? (
                    <div style={{ background: '#FFFFFF', border: '1px solid #DDEC90', borderRadius: '8px', padding: '24px' }}>
                      <div style={{ height: '24px', width: '200px', background: '#F5F8D0', borderRadius: '4px', marginBottom: '16px', opacity: 0.5 }} />
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {[1, 2, 3].map(i => (
                          <div key={i} style={{ height: '48px', background: '#F5F8D0', borderRadius: '4px', opacity: 0.3 }} />
                        ))}
                      </div>
                    </div>
                  ) : (
                    <ProjectTable
                      projects={projectList}
                      onOpenProject={handleOpenProject}
                      onDeleteProject={(name) => setProjectToDelete(name)}
                    />
                  )}
                </div>
                <div>
                  <AgentRoster />
                </div>
              </div>

              {/* Token Usage */}
              <div style={{ marginBottom: '18px' }}>
                <TokenUsagePanel />
              </div>

              {/* Live Orchestration */}
              <div style={{ marginBottom: '18px' }}>
                <LiveOrchestration projectName={firstProject?.name} />
              </div>
            </>
          )}
        </main>
        </div>
      </div>

      {/* Modals */}
      <NewProjectModal
        isOpen={showNewProject}
        onClose={() => setShowNewProject(false)}
        onProjectCreated={handleProjectCreated}
      />

      <ConfirmDialog
        isOpen={projectToDelete !== null}
        title="Delete Project"
        message={`Are you sure you want to delete "${projectToDelete}"? This will unregister the project but preserve its files on disk.`}
        confirmLabel="Delete"
        cancelLabel="Cancel"
        variant="danger"
        isLoading={deleteProject.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setProjectToDelete(null)}
      />
    </div>
  )
}
