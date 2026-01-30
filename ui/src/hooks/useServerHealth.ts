import { useState, useEffect, useCallback, useRef } from 'react'

interface ServerHealthState {
  isHealthy: boolean
  lastCheck: Date | null
  consecutiveFailures: number
  isRecovering: boolean
}

const HEALTH_CHECK_INTERVAL = 10000 // 10 seconds
const MAX_FAILURES_BEFORE_WARNING = 3

/**
 * Hook to monitor server health and provide reconnection status
 */
export function useServerHealth() {
  const [state, setState] = useState<ServerHealthState>({
    isHealthy: true,
    lastCheck: null,
    consecutiveFailures: 0,
    isRecovering: false,
  })

  const checkIntervalRef = useRef<number | null>(null)

  const checkHealth = useCallback(async () => {
    try {
      const response = await fetch('/api/health', {
        method: 'GET',
        // Short timeout to detect quickly
        signal: AbortSignal.timeout(5000),
      })

      if (response.ok) {
        setState(prev => ({
          isHealthy: true,
          lastCheck: new Date(),
          consecutiveFailures: 0,
          isRecovering: prev.consecutiveFailures >= MAX_FAILURES_BEFORE_WARNING,
        }))
      } else {
        throw new Error('Health check failed')
      }
    } catch {
      setState(prev => ({
        ...prev,
        isHealthy: prev.consecutiveFailures < MAX_FAILURES_BEFORE_WARNING - 1,
        lastCheck: new Date(),
        consecutiveFailures: prev.consecutiveFailures + 1,
        isRecovering: false,
      }))
    }
  }, [])

  // Start health check interval
  useEffect(() => {
    // Initial check
    checkHealth()

    // Set up interval
    checkIntervalRef.current = window.setInterval(checkHealth, HEALTH_CHECK_INTERVAL)

    return () => {
      if (checkIntervalRef.current) {
        clearInterval(checkIntervalRef.current)
      }
    }
  }, [checkHealth])

  // Trigger immediate check (e.g., after user clicks "Retry")
  const retryNow = useCallback(() => {
    checkHealth()
  }, [checkHealth])

  return {
    ...state,
    retryNow,
    showWarning: state.consecutiveFailures >= MAX_FAILURES_BEFORE_WARNING,
  }
}
