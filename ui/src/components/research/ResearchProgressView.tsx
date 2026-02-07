/**
 * ResearchProgressView Component
 *
 * Displays real-time progress while the Research Agent analyzes a codebase.
 * Shows phase indicators, progress bar, statistics, and terminal-style logs.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Microscope, FileSearch, Brain, FileText, CheckCircle, Square, ChevronDown, ChevronUp, ArrowRight } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useProjectWebSocket } from '@/hooks/useWebSocket'
import type { ResearchPhase, ResearchLogEntry } from '@/lib/types'

// Fetch research status from API
async function fetchResearchStatus(projectName: string) {
  const response = await fetch(`/api/projects/${encodeURIComponent(projectName)}/agent/research/status`)
  if (!response.ok) {
    throw new Error('Failed to fetch research status')
  }
  return response.json()
}

interface ResearchProgressViewProps {
  projectName: string
}

// Phase configuration with labels, descriptions, and progress ranges
const PHASE_CONFIG: Record<ResearchPhase, {
  label: string
  description: string
  icon: React.ReactNode
  progressMin: number
  progressMax: number
}> = {
  idle: {
    label: 'Starting...',
    description: 'Preparing to analyze codebase',
    icon: <Microscope className="size-5" />,
    progressMin: 0,
    progressMax: 5,
  },
  scanning: {
    label: 'Scanning files...',
    description: 'Discovering project structure and files',
    icon: <FileSearch className="size-5" />,
    progressMin: 5,
    progressMax: 25,
  },
  analyzing: {
    label: 'Analyzing code patterns...',
    description: 'Understanding architecture and patterns',
    icon: <Brain className="size-5" />,
    progressMin: 25,
    progressMax: 75,
  },
  documenting: {
    label: 'Generating documentation...',
    description: 'Writing research findings',
    icon: <FileText className="size-5" />,
    progressMin: 75,
    progressMax: 95,
  },
  complete: {
    label: 'Analysis complete!',
    description: 'Research documentation is ready',
    icon: <CheckCircle className="size-5" />,
    progressMin: 100,
    progressMax: 100,
  },
}

// Research Agent Mascot SVG component
function ResearchAgentMascot({ phase, size = 48 }: { phase: ResearchPhase; size?: number }) {
  // Determine animation class based on phase
  const animationClass = phase === 'idle' ? 'animate-pulse' :
                         phase === 'scanning' ? 'animate-working' :
                         phase === 'analyzing' ? 'animate-thinking' :
                         phase === 'documenting' ? 'animate-working' :
                         phase === 'complete' ? 'animate-celebrate' : ''

  // Colors for the research agent
  const COLORS = {
    primary: '#10B981',    // Emerald-500
    secondary: '#34D399',  // Emerald-400
    accent: '#D1FAE5',     // Emerald-100
    lens: '#60A5FA',       // Blue-400
  }

  return (
    <div
      className={`rounded-full p-2 transition-all duration-300 ${animationClass}`}
      style={{ backgroundColor: COLORS.accent }}
    >
      <svg width={size} height={size} viewBox="0 0 64 64" fill="none">
        {/* Robot body */}
        <rect x="18" y="28" width="28" height="26" rx="4" fill={COLORS.primary} />

        {/* Lab coat */}
        <rect x="20" y="32" width="24" height="18" rx="2" fill="white" />
        <rect x="30" y="32" width="4" height="18" fill={COLORS.secondary} opacity="0.3" />

        {/* Robot head */}
        <rect x="16" y="6" width="32" height="24" rx="4" fill={COLORS.secondary} />

        {/* Antenna */}
        <line x1="32" y1="0" x2="32" y2="6" stroke={COLORS.primary} strokeWidth="2" />
        <circle cx="32" cy="0" r="3" fill={COLORS.primary}>
          {phase !== 'idle' && phase !== 'complete' && (
            <animate attributeName="fill" values={`${COLORS.primary};${COLORS.lens};${COLORS.primary}`} dur="1s" repeatCount="indefinite" />
          )}
        </circle>

        {/* Eyes - one regular, one with magnifying glass */}
        <circle cx="24" cy="16" r="4" fill="white" />
        <circle cx="25" cy="16" r="2" fill={COLORS.primary} />

        {/* Magnifying glass eye */}
        <circle cx="40" cy="16" r="5" fill={COLORS.lens} opacity="0.3" />
        <circle cx="40" cy="16" r="4" fill="white" />
        <circle cx="41" cy="16" r="2" fill={COLORS.primary} />
        <line x1="44" y1="20" x2="48" y2="24" stroke={COLORS.primary} strokeWidth="2" strokeLinecap="round" />

        {/* Smile */}
        <path d="M26,22 Q32,26 38,22" stroke="white" strokeWidth="2" fill="none" strokeLinecap="round" />

        {/* Arms */}
        <rect x="8" y="34" width="10" height="4" rx="2" fill={COLORS.primary} />
        <rect x="46" y="34" width="10" height="4" rx="2" fill={COLORS.primary} />

        {/* Clipboard in hand */}
        <rect x="50" y="38" width="8" height="10" rx="1" fill="#FEF3C7" stroke={COLORS.primary} strokeWidth="1" />
        <line x1="52" y1="42" x2="56" y2="42" stroke={COLORS.primary} strokeWidth="1" />
        <line x1="52" y1="44" x2="55" y2="44" stroke={COLORS.primary} strokeWidth="1" />
        <line x1="52" y1="46" x2="56" y2="46" stroke={COLORS.primary} strokeWidth="1" />

        {/* Status indicator sparkles when analyzing or documenting */}
        {(phase === 'analyzing' || phase === 'documenting') && (
          <>
            <text x="4" y="20" fontSize="8" fill={COLORS.secondary} className="animate-pulse">*</text>
            <text x="58" y="48" fontSize="8" fill={COLORS.secondary} className="animate-pulse" style={{ animationDelay: '0.3s' }}>*</text>
          </>
        )}
      </svg>
    </div>
  )
}

// Calculate progress percentage based on phase AND actual metrics
function calculateProgress(
  phase: ResearchPhase,
  filesScanned: number = 0,
  findingsCount: number = 0
): number {
  // Base progress from phase
  const config = PHASE_CONFIG[phase]

  switch (phase) {
    case 'idle':
      return 5

    case 'scanning': {
      // 5-25%: Progress based on files scanned (estimate ~50 files typical)
      const scanProgress = Math.min(filesScanned / 50, 1)
      return 5 + scanProgress * 20
    }

    case 'analyzing': {
      // 25-75%: Progress based on findings (estimate ~25 findings typical)
      const analyzeProgress = Math.min(findingsCount / 25, 1)
      return 25 + analyzeProgress * 50
    }

    case 'documenting':
      // 75-95%: Linear progress during documentation
      return 85

    case 'complete':
      return 100

    default:
      return (config.progressMin + config.progressMax) / 2
  }
}

// Format timestamp for log display
function formatLogTime(timestamp: string): string {
  try {
    const date = new Date(timestamp)
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return '--:--:--'
  }
}

export function ResearchProgressView({ projectName }: ResearchProgressViewProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { researchState: wsResearchState, isConnected, clearResearchState } = useProjectWebSocket(projectName)
  const [isLogsExpanded, setIsLogsExpanded] = useState(true)
  const [isStopping, setIsStopping] = useState(false)
  const logsEndRef = useRef<HTMLDivElement>(null)
  const maxProgressRef = useRef<number>(0) // Track highest progress to prevent going backwards

  // Reset maxProgress, clear stale WebSocket state, and invalidate query cache on mount
  useEffect(() => {
    maxProgressRef.current = 0
    clearResearchState()
    // Invalidate query cache to ensure fresh data
    queryClient.invalidateQueries({ queryKey: ['researchStatus', projectName] })
  }, [projectName, clearResearchState, queryClient])

  // Poll research status from API to get current state (especially if we missed WebSocket updates)
  const { data: apiStatus } = useQuery({
    queryKey: ['researchStatus', projectName],
    queryFn: () => fetchResearchStatus(projectName),
    refetchInterval: 1000, // Poll every 1 second for responsive updates
    staleTime: 0, // Always consider data stale
    gcTime: 0, // Don't cache results
    enabled: !!projectName,
  })

  // Merge WebSocket state with API status
  // API is authoritative for ALL metrics (phase, filesScanned, findingsCount)
  // WebSocket only provides real-time activity logs
  const researchState = (() => {
    // API is the source of truth for metrics
    const apiState = apiStatus ? {
      phase: (apiStatus.phase ?? 'idle') as ResearchPhase,
      filesScanned: apiStatus.files_scanned ?? 0,
      findingsCount: apiStatus.findings_count ?? 0,
      finalized: apiStatus.finalized ?? false,
      currentTool: wsResearchState?.currentTool ?? null,
      filesWritten: [] as string[],
      logs: wsResearchState?.logs ?? [],
    } : null

    // If no API data yet, use WebSocket state but with 0 counts (they're unreliable)
    if (!apiState && wsResearchState) {
      return {
        ...wsResearchState,
        filesScanned: 0, // WebSocket can't track this reliably
        findingsCount: 0, // WebSocket can't track this reliably
      }
    }

    return apiState
  })()

  // Scroll to bottom of logs when new entries arrive
  useEffect(() => {
    if (isLogsExpanded && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [researchState?.logs, isLogsExpanded])

  // Stop analysis handler
  const handleStopAnalysis = useCallback(async () => {
    setIsStopping(true)
    try {
      const response = await fetch(`/api/projects/${encodeURIComponent(projectName)}/agent/research/stop`, {
        method: 'POST',
      })
      if (!response.ok) {
        const error = await response.json().catch(() => ({ message: 'Unknown error' }))
        console.error('Failed to stop research agent:', error)
      } else {
        // Navigate back to project after stopping
        navigate(`/?project=${encodeURIComponent(projectName)}`)
      }
    } catch (error) {
      console.error('Error stopping research agent:', error)
    } finally {
      setIsStopping(false)
    }
  }, [projectName, navigate])

  // Navigate to results handler
  const handleViewResults = useCallback(() => {
    navigate(`/research/${encodeURIComponent(projectName)}/results`)
  }, [navigate, projectName])

  // Derive current phase - default to idle if no research state
  const currentPhase: ResearchPhase = researchState?.phase ?? 'idle'
  const phaseConfig = PHASE_CONFIG[currentPhase]

  // Calculate progress based on actual metrics
  const filesScanned = researchState?.filesScanned ?? 0
  const findingsCount = researchState?.findingsCount ?? 0
  const rawProgress = calculateProgress(currentPhase, filesScanned, findingsCount)

  // Reset progress when a new research starts or no research exists
  // Detected by: phase is null/idle, or scanning with 0 findings
  if (!currentPhase || currentPhase === 'idle' || (currentPhase === 'scanning' && findingsCount === 0)) {
    maxProgressRef.current = 0
  }

  // Progress should never go backwards (except on reset)
  if (rawProgress > maxProgressRef.current) {
    maxProgressRef.current = rawProgress
  }
  const progress = maxProgressRef.current

  const isComplete = currentPhase === 'complete'
  const logs = researchState?.logs ?? []

  return (
    <div className="space-y-6 p-6 max-w-4xl mx-auto">
      {/* Main Progress Card */}
      <Card className="overflow-hidden">
        <CardHeader className="bg-gradient-to-r from-emerald-50 to-teal-50 dark:from-emerald-950/30 dark:to-teal-950/30 border-b border-emerald-200 dark:border-emerald-800/50">
          <div className="flex items-center gap-4">
            <ResearchAgentMascot phase={currentPhase} size={56} />
            <div className="flex-1 min-w-0">
              <CardTitle className="flex items-center gap-2 text-emerald-700 dark:text-emerald-300">
                {phaseConfig.icon}
                <span>{phaseConfig.label}</span>
                {!isConnected && (
                  <Badge variant="outline" className="ml-2 text-amber-600 border-amber-400">
                    Reconnecting...
                  </Badge>
                )}
              </CardTitle>
              <p className="text-sm text-muted-foreground mt-1">
                {phaseConfig.description}
              </p>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-2">
              {isComplete ? (
                <Button
                  onClick={handleViewResults}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white"
                >
                  View Results
                  <ArrowRight className="size-4 ml-1" />
                </Button>
              ) : (
                <Button
                  variant="destructive"
                  onClick={handleStopAnalysis}
                  disabled={isStopping}
                >
                  <Square className="size-4 mr-1" />
                  {isStopping ? 'Stopping...' : 'Stop Analysis'}
                </Button>
              )}
            </div>
          </div>
        </CardHeader>

        <CardContent className="p-6 space-y-6">
          {/* Progress Bar */}
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">Progress</span>
              <span className="font-medium">{Math.round(progress)}%</span>
            </div>
            <div className="h-3 bg-muted rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-500 ease-out ${
                  isComplete
                    ? 'bg-emerald-500'
                    : 'bg-gradient-to-r from-emerald-400 to-teal-400'
                }`}
                style={{ width: `${progress}%` }}
              >
                {!isComplete && (
                  <div className="h-full w-full bg-white/20 animate-pulse" />
                )}
              </div>
            </div>
          </div>

          {/* Phase Indicators */}
          <div className="flex justify-between items-center">
            {(['scanning', 'analyzing', 'documenting', 'complete'] as ResearchPhase[]).map((phase, idx) => {
              const config = PHASE_CONFIG[phase]
              const isActive = currentPhase === phase
              const isPast = PHASE_CONFIG[currentPhase].progressMin >= config.progressMin

              return (
                <div
                  key={phase}
                  className={`flex flex-col items-center gap-1 flex-1 ${
                    idx > 0 ? 'border-l border-border' : ''
                  }`}
                >
                  <div
                    className={`p-2 rounded-full transition-colors ${
                      isActive
                        ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/50 dark:text-emerald-400'
                        : isPast
                          ? 'bg-emerald-50 text-emerald-500 dark:bg-emerald-950/30 dark:text-emerald-500'
                          : 'bg-muted text-muted-foreground'
                    }`}
                  >
                    {config.icon}
                  </div>
                  <span
                    className={`text-xs font-medium text-center ${
                      isActive ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'
                    }`}
                  >
                    {config.label.replace('...', '')}
                  </span>
                </div>
              )
            })}
          </div>

          {/* Stats Row */}
          <div className="grid grid-cols-2 gap-4">
            <div className="p-4 bg-muted/50 rounded-lg">
              <div className="flex items-center gap-2 text-muted-foreground text-sm mb-1">
                <FileSearch className="size-4" />
                Files Scanned
              </div>
              <div className="text-2xl font-bold">
                {researchState?.filesScanned ?? 0}
              </div>
            </div>
            <div className="p-4 bg-muted/50 rounded-lg">
              <div className="flex items-center gap-2 text-muted-foreground text-sm mb-1">
                <Brain className="size-4" />
                Findings
              </div>
              <div className="text-2xl font-bold">
                {researchState?.findingsCount ?? 0}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Logs Panel */}
      <Card>
        <button
          onClick={() => setIsLogsExpanded(!isLogsExpanded)}
          className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/50 transition-colors"
        >
          <div className="flex items-center gap-2">
            <FileText className="size-4 text-muted-foreground" />
            <span className="font-medium">Activity Log</span>
            <Badge variant="secondary" className="text-xs">
              {logs.length}
            </Badge>
          </div>
          {isLogsExpanded ? (
            <ChevronUp className="size-4 text-muted-foreground" />
          ) : (
            <ChevronDown className="size-4 text-muted-foreground" />
          )}
        </button>

        {isLogsExpanded && (
          <CardContent className="p-0 border-t">
            <ScrollArea className="h-64">
              <div className="p-4 font-mono text-sm space-y-1">
                {logs.length === 0 ? (
                  <div className="text-muted-foreground text-center py-8">
                    Waiting for activity...
                  </div>
                ) : (
                  logs.map((log: ResearchLogEntry, idx: number) => (
                    <div
                      key={`${log.timestamp}-${idx}`}
                      className="flex gap-3 py-1 hover:bg-muted/30 rounded px-2 -mx-2"
                    >
                      <span className="text-muted-foreground shrink-0 tabular-nums">
                        {formatLogTime(log.timestamp)}
                      </span>
                      <span
                        className={
                          log.eventType === 'research_complete' || log.eventType === 'research_finalized'
                            ? 'text-emerald-600 dark:text-emerald-400'
                            : log.eventType.includes('error')
                              ? 'text-destructive'
                              : 'text-foreground'
                        }
                      >
                        {log.message}
                      </span>
                    </div>
                  ))
                )}
                <div ref={logsEndRef} />
              </div>
            </ScrollArea>
          </CardContent>
        )}
      </Card>
    </div>
  )
}
