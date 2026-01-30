import { AlertTriangle, RefreshCw, CheckCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useServerHealth } from '../hooks/useServerHealth'

/**
 * Banner that appears when server connection is lost
 */
export function ServerStatusBanner() {
  const { showWarning, isRecovering, consecutiveFailures, retryNow } = useServerHealth()

  // Show recovery message briefly when connection is restored
  if (isRecovering) {
    return (
      <div className="bg-green-500/10 border-b border-green-500/30 px-4 py-2">
        <div className="flex items-center justify-center gap-2 text-green-600 dark:text-green-400 text-sm">
          <CheckCircle size={16} />
          <span>Server connection restored</span>
        </div>
      </div>
    )
  }

  // Only show warning after 3+ consecutive failures
  if (!showWarning) {
    return null
  }

  return (
    <div className="bg-destructive/10 border-b border-destructive/30 px-4 py-2">
      <div className="flex items-center justify-between max-w-screen-xl mx-auto">
        <div className="flex items-center gap-2 text-destructive text-sm">
          <AlertTriangle size={16} />
          <span>
            Unable to connect to server
            {consecutiveFailures > 3 && ` (${consecutiveFailures} failed attempts)`}
          </span>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={retryNow}
          className="text-destructive border-destructive/50 hover:bg-destructive/10"
        >
          <RefreshCw size={14} className="mr-1" />
          Retry
        </Button>
      </div>
    </div>
  )
}
