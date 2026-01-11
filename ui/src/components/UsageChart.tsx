import { useMemo } from 'react'

interface TimelineEntry {
  date: string
  tokens: number
  cost: number
  sessions: number
}

interface UsageChartProps {
  data: TimelineEntry[]
  height?: number
  showCost?: boolean
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function formatTokens(tokens: number): string {
  if (tokens >= 1_000_000) {
    return `${(tokens / 1_000_000).toFixed(1)}M`
  }
  if (tokens >= 1_000) {
    return `${(tokens / 1_000).toFixed(0)}K`
  }
  return tokens.toString()
}

export function UsageChart({ data, height = 200, showCost = false }: UsageChartProps) {
  const chartData = useMemo(() => {
    if (data.length === 0) return null

    const maxTokens = Math.max(...data.map(d => d.tokens), 1)
    const maxCost = Math.max(...data.map(d => d.cost), 0.01)

    return {
      entries: data.map(d => ({
        ...d,
        tokenHeight: (d.tokens / maxTokens) * 100,
        costHeight: (d.cost / maxCost) * 100,
      })),
      maxTokens,
      maxCost,
    }
  }, [data])

  if (!chartData || data.length === 0) {
    return (
      <div
        className="flex items-center justify-center text-[var(--color-neo-text-secondary)]"
        style={{ height }}
      >
        No usage data available
      </div>
    )
  }

  const barWidth = Math.max(20, Math.min(60, (100 / data.length) - 2))

  return (
    <div className="space-y-2">
      {/* Chart area */}
      <div className="relative" style={{ height }}>
        {/* Y-axis labels */}
        <div className="absolute left-0 top-0 bottom-0 w-12 flex flex-col justify-between text-xs text-[var(--color-neo-text-secondary)]">
          <span>{formatTokens(chartData.maxTokens)}</span>
          <span>{formatTokens(chartData.maxTokens / 2)}</span>
          <span>0</span>
        </div>

        {/* Chart content */}
        <div className="ml-14 h-full flex items-end justify-between gap-1 border-l border-b border-[var(--color-neo-border)]">
          {chartData.entries.map((entry, i) => (
            <div
              key={entry.date}
              className="flex flex-col items-center gap-1 group relative"
              style={{ width: `${barWidth}px` }}
            >
              {/* Token bar */}
              <div
                className="w-full bg-[var(--color-neo-progress)] rounded-t transition-all hover:bg-[var(--color-neo-accent)]"
                style={{
                  height: `${entry.tokenHeight}%`,
                  minHeight: entry.tokens > 0 ? '4px' : '0',
                }}
              />

              {/* Cost bar (stacked) */}
              {showCost && (
                <div
                  className="w-full bg-amber-500 rounded-t opacity-70"
                  style={{
                    height: `${entry.costHeight * 0.3}%`,
                    minHeight: entry.cost > 0 ? '2px' : '0',
                  }}
                />
              )}

              {/* Tooltip */}
              <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 opacity-0 group-hover:opacity-100 transition-opacity z-10 pointer-events-none">
                <div className="neo-card p-2 text-xs whitespace-nowrap shadow-lg">
                  <div className="font-bold">{formatDate(entry.date)}</div>
                  <div>Tokens: {formatTokens(entry.tokens)}</div>
                  <div>Cost: ${entry.cost.toFixed(2)}</div>
                  <div>Sessions: {entry.sessions}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* X-axis labels */}
      <div className="ml-14 flex justify-between text-xs text-[var(--color-neo-text-secondary)]">
        {chartData.entries.length <= 7 ? (
          // Show all labels for 7 or fewer entries
          chartData.entries.map(entry => (
            <span key={entry.date} style={{ width: `${barWidth}px` }} className="text-center truncate">
              {formatDate(entry.date)}
            </span>
          ))
        ) : (
          // Show first, middle, and last for more entries
          <>
            <span>{formatDate(chartData.entries[0].date)}</span>
            <span>{formatDate(chartData.entries[Math.floor(chartData.entries.length / 2)].date)}</span>
            <span>{formatDate(chartData.entries[chartData.entries.length - 1].date)}</span>
          </>
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-4 text-xs">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-[var(--color-neo-progress)]" />
          <span>Tokens</span>
        </div>
        {showCost && (
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 rounded bg-amber-500 opacity-70" />
            <span>Cost</span>
          </div>
        )}
      </div>
    </div>
  )
}
