import { BarChart3, TrendingUp, Zap, Calendar, DollarSign, Clock } from 'lucide-react'
import { UsageChart } from './UsageChart'
import { UsageWarning, type UsageLevel } from './UsageWarning'

interface UsageBudget {
  tokens_used: number
  tokens_remaining: number
  tokens_limit: number
  cost_used: number
  cost_remaining: number
  cost_limit: number
  percentage_used: number
}

interface UsageData {
  daily: UsageBudget
  monthly: UsageBudget
  level: UsageLevel
}

interface TimelineEntry {
  date: string
  tokens: number
  cost: number
  sessions: number
}

interface ProjectUsage {
  project_name: string
  total_tokens: number
  cost: number
  sessions: number
}

interface AgentUsage {
  agent_type: string
  total_tokens: number
  cost: number
  calls: number
}

interface UsageDashboardProps {
  usage: UsageData
  timeline: TimelineEntry[]
  projectBreakdown?: ProjectUsage[]
  agentBreakdown?: AgentUsage[]
  onRefresh?: () => void
  isLoading?: boolean
}

function formatTokens(tokens: number): string {
  if (tokens >= 1_000_000) {
    return `${(tokens / 1_000_000).toFixed(1)}M`
  }
  if (tokens >= 1_000) {
    return `${(tokens / 1_000).toFixed(1)}K`
  }
  return tokens.toString()
}

function formatCost(cost: number): string {
  return `$${cost.toFixed(2)}`
}

function BudgetCard({
  title,
  icon,
  used,
  limit,
  percentage,
  formatValue,
}: {
  title: string
  icon: React.ReactNode
  used: number
  limit: number
  percentage: number
  formatValue: (n: number) => string
}) {
  const remaining = limit - used
  const isLow = percentage > 80
  const isCritical = percentage > 95

  return (
    <div className="neo-card p-4">
      <div className="flex items-center gap-2 mb-3">
        <div className="p-2 rounded-lg bg-[var(--color-neo-bg)]">
          {icon}
        </div>
        <h4 className="font-bold">{title}</h4>
      </div>

      {/* Progress bar */}
      <div className="h-3 bg-[var(--color-neo-border)] rounded-full overflow-hidden mb-2">
        <div
          className={`h-full rounded-full transition-all ${
            isCritical
              ? 'bg-red-500'
              : isLow
                ? 'bg-amber-500'
                : 'bg-[var(--color-neo-progress)]'
          }`}
          style={{ width: `${Math.min(100, percentage)}%` }}
        />
      </div>

      {/* Stats */}
      <div className="flex justify-between text-sm">
        <span className="text-[var(--color-neo-text-secondary)]">
          Used: {formatValue(used)}
        </span>
        <span className={`font-bold ${isCritical ? 'text-red-500' : isLow ? 'text-amber-500' : ''}`}>
          {percentage.toFixed(1)}%
        </span>
      </div>
      <div className="flex justify-between text-sm text-[var(--color-neo-text-secondary)]">
        <span>Remaining: {formatValue(remaining)}</span>
        <span>Limit: {formatValue(limit)}</span>
      </div>
    </div>
  )
}

function BreakdownTable({
  title,
  data,
  columns,
}: {
  title: string
  data: { name: string; tokens: number; cost: number; secondary?: number }[]
  columns: { header: string; accessor: keyof typeof data[0] }[]
}) {
  if (data.length === 0) return null

  return (
    <div className="neo-card p-4">
      <h4 className="font-bold mb-3">{title}</h4>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[var(--color-neo-border)]">
              {columns.map(col => (
                <th key={col.header} className="text-left py-2 px-2 font-bold">
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.map((row, i) => (
              <tr key={i} className="border-b border-[var(--color-neo-border)] last:border-0">
                <td className="py-2 px-2 font-medium">{row.name}</td>
                <td className="py-2 px-2">{formatTokens(row.tokens)}</td>
                <td className="py-2 px-2">{formatCost(row.cost)}</td>
                {row.secondary !== undefined && (
                  <td className="py-2 px-2 text-[var(--color-neo-text-secondary)]">
                    {row.secondary}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function UsageDashboard({
  usage,
  timeline,
  projectBreakdown,
  agentBreakdown,
  onRefresh,
  isLoading,
}: UsageDashboardProps) {
  return (
    <div className="space-y-6 p-4">
      {/* Warning Banner */}
      <UsageWarning
        level={usage.level}
        dailyPercentage={usage.daily.percentage_used}
        monthlyPercentage={usage.monthly.percentage_used}
      />

      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="font-display font-bold text-xl flex items-center gap-2">
          <BarChart3 size={24} />
          Usage Dashboard
        </h2>
        {onRefresh && (
          <button
            onClick={onRefresh}
            disabled={isLoading}
            className="neo-button flex items-center gap-2"
          >
            <TrendingUp size={16} className={isLoading ? 'animate-spin' : ''} />
            Refresh
          </button>
        )}
      </div>

      {/* Budget Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <BudgetCard
          title="Daily Tokens"
          icon={<Zap size={18} />}
          used={usage.daily.tokens_used}
          limit={usage.daily.tokens_limit}
          percentage={usage.daily.percentage_used}
          formatValue={formatTokens}
        />
        <BudgetCard
          title="Daily Cost"
          icon={<DollarSign size={18} />}
          used={usage.daily.cost_used}
          limit={usage.daily.cost_limit}
          percentage={(usage.daily.cost_used / usage.daily.cost_limit) * 100}
          formatValue={formatCost}
        />
        <BudgetCard
          title="Monthly Tokens"
          icon={<Calendar size={18} />}
          used={usage.monthly.tokens_used}
          limit={usage.monthly.tokens_limit}
          percentage={usage.monthly.percentage_used}
          formatValue={formatTokens}
        />
        <BudgetCard
          title="Monthly Cost"
          icon={<Clock size={18} />}
          used={usage.monthly.cost_used}
          limit={usage.monthly.cost_limit}
          percentage={(usage.monthly.cost_used / usage.monthly.cost_limit) * 100}
          formatValue={formatCost}
        />
      </div>

      {/* Usage Chart */}
      <div className="neo-card p-4">
        <h4 className="font-bold mb-4">Usage Over Time</h4>
        <UsageChart data={timeline} />
      </div>

      {/* Breakdowns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {projectBreakdown && projectBreakdown.length > 0 && (
          <BreakdownTable
            title="Usage by Project"
            data={projectBreakdown.map(p => ({
              name: p.project_name,
              tokens: p.total_tokens,
              cost: p.cost,
              secondary: p.sessions,
            }))}
            columns={[
              { header: 'Project', accessor: 'name' },
              { header: 'Tokens', accessor: 'tokens' },
              { header: 'Cost', accessor: 'cost' },
              { header: 'Sessions', accessor: 'secondary' },
            ]}
          />
        )}
        {agentBreakdown && agentBreakdown.length > 0 && (
          <BreakdownTable
            title="Usage by Agent Type"
            data={agentBreakdown.map(a => ({
              name: a.agent_type,
              tokens: a.total_tokens,
              cost: a.cost,
              secondary: a.calls,
            }))}
            columns={[
              { header: 'Agent', accessor: 'name' },
              { header: 'Tokens', accessor: 'tokens' },
              { header: 'Cost', accessor: 'cost' },
              { header: 'Calls', accessor: 'secondary' },
            ]}
          />
        )}
      </div>
    </div>
  )
}
