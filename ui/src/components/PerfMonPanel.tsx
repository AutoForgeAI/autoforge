import { useEffect, useRef, useState } from 'react'
import { Activity } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader } from '@/components/ui/card'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { usePerfMonMock } from '@/hooks/usePerfMonMock'
import type { PerfMetrics } from '@/lib/types'

interface PerfMonPanelProps {
  isLive: boolean
  perfMetrics: PerfMetrics | null
}

function StatBar({ value }: { value: number | null }) {
  const width = value === null ? 0 : Math.min(100, Math.max(0, value))

  return (
    <div className="h-2 w-full rounded-full bg-muted">
      {value !== null && (
        <div
          className="h-2 rounded-full bg-primary transition-[width] duration-300 ease-out"
          style={{ width: `${width}%` }}
        />
      )}
    </div>
  )
}

function formatValue(value: number | null, decimals = 0) {
  if (value === null) return 'Not available'
  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
}

export function PerfMonPanel({ isLive, perfMetrics }: PerfMonPanelProps) {
  const [isOpen, setIsOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const mockMetrics = usePerfMonMock(isLive)
  const allowMockFallback = import.meta.env.DEV && import.meta.env.VITE_PERFMON_MOCK !== '0'
  const usingLive = !!perfMetrics
  const usingMock = !usingLive && allowMockFallback

  const lastUpdateMs = perfMetrics ? Date.parse(perfMetrics.timestamp) : null
  const isStale = lastUpdateMs !== null && Number.isFinite(lastUpdateMs) && (Date.now() - lastUpdateMs > 10_000)

  const tokenCurrentRun = perfMetrics
    ? (perfMetrics.tokens.available ? perfMetrics.tokens.current_run : null)
    : (usingMock ? mockMetrics.tokens.currentRun : null)

  const tokenTotalSession = perfMetrics
    ? (perfMetrics.tokens.available ? perfMetrics.tokens.total_session : null)
    : (usingMock ? mockMetrics.tokens.totalSession : null)

  const tokenUsagePercent = perfMetrics
    ? (perfMetrics.tokens.available && perfMetrics.tokens.current_run !== null
      ? Math.min(100, Math.max(0, (perfMetrics.tokens.current_run / 5000) * 100))
      : null)
    : (usingMock ? mockMetrics.tokens.usagePercent : null)

  const cpuPercent = perfMetrics ? perfMetrics.cpu.percent : (usingMock ? mockMetrics.cpu.percent : null)
  const memoryUsedGb = perfMetrics ? perfMetrics.memory.used_gb : (usingMock ? mockMetrics.memory.used : null)
  const memoryTotalGb = perfMetrics ? perfMetrics.memory.total_gb : (usingMock ? mockMetrics.memory.total : null)
  const memoryPercent = perfMetrics ? perfMetrics.memory.percent : (usingMock ? mockMetrics.memory.percent : null)

  const gpuAvailable = perfMetrics ? perfMetrics.gpu.available : usingMock
  const gpuPercent = perfMetrics
    ? (perfMetrics.gpu.available ? perfMetrics.gpu.percent : null)
    : (usingMock ? mockMetrics.gpu.percent : null)
  const gpuVramUsed = perfMetrics
    ? (perfMetrics.gpu.available ? perfMetrics.gpu.vram_used_gb : null)
    : (usingMock ? mockMetrics.gpu.used : null)
  const gpuVramTotal = perfMetrics
    ? (perfMetrics.gpu.available ? perfMetrics.gpu.vram_total_gb : null)
    : (usingMock ? mockMetrics.gpu.total : null)

  useEffect(() => {
    if (!isOpen) return

    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleEscape)

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [isOpen])

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              onClick={() => setIsOpen(prev => !prev)}
              variant="outline"
              size="sm"
              aria-label="PerfMon"
              aria-expanded={isOpen}
              aria-haspopup="dialog"
            >
              <Activity size={18} />
            </Button>
          </TooltipTrigger>
          <TooltipContent>PerfMon</TooltipContent>
        </Tooltip>
        <Badge
          variant={isLive ? 'default' : 'secondary'}
          className="pointer-events-none absolute -top-2 -right-3 px-1.5 py-0 text-[10px]"
        >
          {isLive ? 'Live' : 'Idle'}
        </Badge>
      </div>

      {isOpen && (
        <Card className="absolute right-0 top-full z-40 mt-3 w-80 gap-4 p-0 shadow-lg">
          <CardHeader className="flex-row items-center justify-between space-y-0 border-b px-4 py-3">
            <div className="text-sm font-semibold uppercase tracking-wide">PerfMon</div>
            <div className="flex items-center gap-2">
              {isStale && (
                <Badge variant="outline" className="text-[10px] px-2 py-0.5">
                  Stale
                </Badge>
              )}
              <Badge variant={isLive ? 'default' : 'secondary'} className="text-[10px] px-2 py-0.5">
                {isLive ? 'Live' : 'Idle'}
              </Badge>
            </div>
          </CardHeader>
          <CardContent className={`px-4 pb-4 space-y-4 ${isStale ? 'opacity-75' : ''}`}>
            {!usingLive && !usingMock && (
              <div className="rounded border border-border bg-muted/20 px-2 py-1 text-xs text-muted-foreground">
                Live telemetry not available.
              </div>
            )}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Tokens · Current run</span>
                <span className="font-medium text-foreground">
                  {tokenCurrentRun === null ? 'Not available' : tokenCurrentRun.toLocaleString()}
                </span>
              </div>
              <StatBar value={tokenUsagePercent} />
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Total session</span>
                <span className="font-medium text-foreground">
                  {tokenTotalSession === null ? 'Not available' : tokenTotalSession.toLocaleString()}
                </span>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>CPU</span>
                  <span className="font-medium text-foreground">
                    {cpuPercent === null ? 'Not available' : `${Math.round(cpuPercent)}%`}
                  </span>
                </div>
                <StatBar value={cpuPercent} />
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Memory</span>
                  <span className="font-medium text-foreground">
                    {memoryUsedGb === null || memoryTotalGb === null
                      ? 'Not available'
                      : `${formatValue(memoryUsedGb, 1)} / ${formatValue(memoryTotalGb, 1)} GB`}
                  </span>
                </div>
                <StatBar value={memoryPercent} />
              </div>
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>GPU</span>
                {gpuAvailable ? (
                  <span className="font-medium text-foreground">
                    {gpuPercent === null ? 'Not available' : `${Math.round(gpuPercent)}%`}
                  </span>
                ) : (
                  <span className="text-muted-foreground">Not available</span>
                )}
              </div>
              {gpuAvailable ? (
                <>
                  <StatBar value={gpuPercent} />
                  <div className="text-xs text-muted-foreground">
                    {gpuVramUsed === null || gpuVramTotal === null
                      ? 'VRAM Not available'
                      : `VRAM ${formatValue(gpuVramUsed, 1)} / ${formatValue(gpuVramTotal, 1)} GB`}
                  </div>
                </>
              ) : null}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
