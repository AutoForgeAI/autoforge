import { AlertTriangle, AlertCircle, XCircle, CheckCircle2, X } from 'lucide-react'
import { useState } from 'react'

export type UsageLevel = 'critical' | 'low' | 'moderate' | 'healthy'

interface UsageWarningProps {
  level: UsageLevel
  dailyPercentage: number
  monthlyPercentage: number
  onDismiss?: () => void
  showDetails?: boolean
}

function getLevelConfig(level: UsageLevel) {
  switch (level) {
    case 'critical':
      return {
        icon: XCircle,
        bgColor: 'bg-red-50',
        borderColor: 'border-red-500',
        textColor: 'text-red-700',
        iconColor: 'text-red-500',
        title: 'Critical Usage',
        message: 'Usage is critically high. Agent work has been paused to prevent exceeding limits.',
        showAlways: true,
      }
    case 'low':
      return {
        icon: AlertTriangle,
        bgColor: 'bg-amber-50',
        borderColor: 'border-amber-500',
        textColor: 'text-amber-700',
        iconColor: 'text-amber-500',
        title: 'Low Remaining Budget',
        message: 'Usage is high. The agent will focus on completing in-progress tasks only.',
        showAlways: true,
      }
    case 'moderate':
      return {
        icon: AlertCircle,
        bgColor: 'bg-blue-50',
        borderColor: 'border-blue-500',
        textColor: 'text-blue-700',
        iconColor: 'text-blue-500',
        title: 'Moderate Usage',
        message: 'Usage is moderate. The agent will prioritize completing features close to done.',
        showAlways: false,
      }
    case 'healthy':
    default:
      return {
        icon: CheckCircle2,
        bgColor: 'bg-green-50',
        borderColor: 'border-green-500',
        textColor: 'text-green-700',
        iconColor: 'text-green-500',
        title: 'Healthy Usage',
        message: 'Usage levels are healthy. Normal operation.',
        showAlways: false,
      }
  }
}

export function UsageWarning({
  level,
  dailyPercentage,
  monthlyPercentage,
  onDismiss,
  showDetails = true,
}: UsageWarningProps) {
  const [isDismissed, setIsDismissed] = useState(false)
  const config = getLevelConfig(level)

  // Don't show healthy/moderate by default, or if dismissed
  if (isDismissed || (!config.showAlways && level !== 'critical')) {
    return null
  }

  const Icon = config.icon

  const handleDismiss = () => {
    setIsDismissed(true)
    onDismiss?.()
  }

  return (
    <div
      className={`
        ${config.bgColor} ${config.borderColor} ${config.textColor}
        border-2 rounded-lg p-4
      `}
    >
      <div className="flex items-start gap-3">
        <Icon size={24} className={`${config.iconColor} flex-shrink-0 mt-0.5`} />

        <div className="flex-1">
          <div className="flex items-center justify-between">
            <h4 className="font-bold">{config.title}</h4>
            {level !== 'critical' && (
              <button
                onClick={handleDismiss}
                className="p-1 hover:bg-black/10 rounded"
              >
                <X size={16} />
              </button>
            )}
          </div>

          <p className="text-sm mt-1">{config.message}</p>

          {showDetails && (
            <div className="flex gap-4 mt-2 text-sm">
              <div>
                <span className="opacity-70">Daily:</span>{' '}
                <span className="font-bold">{dailyPercentage.toFixed(1)}%</span> used
              </div>
              <div>
                <span className="opacity-70">Monthly:</span>{' '}
                <span className="font-bold">{monthlyPercentage.toFixed(1)}%</span> used
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// Compact version for header/status bar
interface UsageIndicatorProps {
  level: UsageLevel
  percentage: number
  onClick?: () => void
}

export function UsageIndicator({ level, percentage, onClick }: UsageIndicatorProps) {
  const config = getLevelConfig(level)
  const Icon = config.icon

  return (
    <button
      onClick={onClick}
      className={`
        flex items-center gap-2 px-3 py-1.5 rounded-lg
        ${config.bgColor} ${config.textColor}
        hover:opacity-80 transition-opacity
      `}
      title={`${config.title}: ${percentage.toFixed(1)}% used`}
    >
      <Icon size={16} className={config.iconColor} />
      <span className="text-sm font-bold">{percentage.toFixed(0)}%</span>
    </button>
  )
}
