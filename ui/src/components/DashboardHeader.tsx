import React from 'react'

interface DashboardHeaderProps {
  projectCount: number
  onNewProject: () => void
  themeControls?: React.ReactNode
  activeTab?: string
  onTabChange?: (tab: string) => void
}

const NAV_TABS = ['DASHBOARD', 'AGENTS', 'ANALYTICS', 'CONFIG'] as const

export function DashboardHeader({ projectCount, activeTab = 'DASHBOARD', onTabChange }: DashboardHeaderProps) {
  return (
    <header
      className="flex items-center h-[52px] px-6 gap-0 sticky top-0 z-50 shrink-0"
      style={{ background: '#1A1A00', borderBottom: '2px solid #2A2A00', fontFamily: "'Inter', sans-serif" }}
    >
      {/* Logo */}
      <div className="text-[22px] font-bold text-white tracking-[-0.3px] shrink-0 mr-8">
        Infini<span style={{ color: '#FFE52A' }}>AI</span>
        <sup
          className="text-[10px] font-normal tracking-[2px] uppercase ml-[3px]"
          style={{ color: '#9A9A60' }}
        >
          OS
        </sup>
      </div>

      {/* Nav tabs */}
      <nav className="flex gap-[2px]">
        {NAV_TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => onTabChange?.(tab)}
            className="text-[14px] font-bold tracking-[0.5px] uppercase px-4 py-1.5 rounded cursor-pointer border-none transition-all"
            style={{
              background: activeTab === tab ? '#BBCB64' : 'transparent',
              color: activeTab === tab ? '#1A1A00' : '#9A9A60',
            }}
            onMouseEnter={e => { if (activeTab !== tab) (e.target as HTMLElement).style.color = '#DDEC90' }}
            onMouseLeave={e => { if (activeTab !== tab) (e.target as HTMLElement).style.color = '#9A9A60' }}
          >
            {tab}
          </button>
        ))}
      </nav>

      <div className="ml-auto flex items-center gap-2.5">
        {/* Active badge */}
        <div
          className="text-[12px] font-bold tracking-[1px] uppercase px-2.5 py-1 rounded-full"
          style={{ background: 'rgba(187,203,100,0.12)', color: '#BBCB64', border: '1px solid rgba(187,203,100,0.25)' }}
        >
          &#9679; {projectCount} Active
        </div>
        {/* HITL badge */}
        <div
          className="text-[12px] font-bold tracking-[1px] uppercase px-2.5 py-1 rounded-full"
          style={{ background: 'rgba(247,154,25,0.12)', color: '#F79A19', border: '1px solid rgba(247,154,25,0.3)' }}
        >
          &#9889; 3 HITL Pending
        </div>
        {/* Avatar */}
        <div
          className="w-[30px] h-[30px] rounded-full flex items-center justify-center text-[14px] font-bold shrink-0"
          style={{ background: '#BBCB64', color: '#1A1A00' }}
        >
          BK
        </div>
      </div>
    </header>
  )
}
