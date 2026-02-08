import { useEffect, useMemo, useRef, useState } from 'react'

const clamp = (value: number, min: number, max: number) =>
  Math.min(max, Math.max(min, value))

const wave = (
  t: number,
  period: number,
  min: number,
  max: number,
  phase = 0
) => {
  const angle = (t / period) * Math.PI * 2 + phase
  const normalized = (Math.sin(angle) + 1) / 2
  return min + (max - min) * normalized
}

export interface PerfMonMetrics {
  tokens: {
    currentRun: number
    totalSession: number
    usagePercent: number
  }
  cpu: {
    percent: number
  }
  memory: {
    used: number
    total: number
    percent: number
  }
  gpu: {
    available: boolean
    percent: number
    used: number
    total: number
  }
}

function buildMetrics(t: number): PerfMonMetrics {
  const currentRun = Math.round(wave(t, 12, 900, 3200))
  const totalSession = Math.round(
    clamp(12000 + t * 28 + wave(t, 22, -300, 300, 0.6), 0, 120000)
  )
  const tokensUsagePercent = clamp((currentRun / 5000) * 100, 0, 100)

  const cpuPercent = Math.round(wave(t, 8, 18, 82, 0.4))

  const memoryTotal = 16
  const memoryUsed = Number(wave(t, 18, 5.4, 12.6, 1.1).toFixed(1))
  const memoryPercent = clamp((memoryUsed / memoryTotal) * 100, 0, 100)

  const gpuAvailable = Math.floor(t / 90) % 2 === 0
  const gpuTotal = 12
  const gpuPercent = Math.round(wave(t, 10, 12, 78, 0.2))
  const gpuUsed = Number(wave(t, 14, 2.8, 7.4, 0.9).toFixed(1))

  return {
    tokens: {
      currentRun,
      totalSession,
      usagePercent: tokensUsagePercent,
    },
    cpu: {
      percent: cpuPercent,
    },
    memory: {
      used: memoryUsed,
      total: memoryTotal,
      percent: memoryPercent,
    },
    gpu: {
      available: gpuAvailable,
      percent: gpuPercent,
      used: gpuUsed,
      total: gpuTotal,
    },
  }
}

export function usePerfMonMock(isRunning: boolean) {
  const startRef = useRef<number>(Date.now())
  const [metrics, setMetrics] = useState<PerfMonMetrics>(() => buildMetrics(0))

  const intervalMs = useMemo(() => (isRunning ? 1000 : 3000), [isRunning])

  useEffect(() => {
    const tick = () => {
      const elapsedSeconds = (Date.now() - startRef.current) / 1000
      setMetrics(buildMetrics(elapsedSeconds))
    }

    tick()
    const interval = setInterval(tick, intervalMs)

    return () => clearInterval(interval)
  }, [intervalMs])

  return metrics
}
