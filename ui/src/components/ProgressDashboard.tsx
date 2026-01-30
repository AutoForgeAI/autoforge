import { Wifi, WifiOff, Zap, PauseCircle, AlertTriangle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'

interface ProgressDashboardProps {
  passing: number
  total: number
  percentage: number
  isConnected: boolean
  yoloMode?: boolean
  pickupPaused?: boolean
  gracefulShutdown?: boolean
}

export function ProgressDashboard({
  passing,
  total,
  percentage,
  isConnected,
  yoloMode = false,
  pickupPaused = false,
  gracefulShutdown = false,
}: ProgressDashboardProps) {
  return (
    <Card className="py-2">
      <CardHeader className="flex-row items-center justify-between space-y-0 pb-2 pt-2">
        <CardTitle className="text-sm uppercase tracking-wide text-muted-foreground">
          Progress
        </CardTitle>
        <div className="flex items-center gap-2">
          {/* YOLO Mode badge */}
          {yoloMode && (
            <Badge variant="secondary" className="gap-1 text-xs py-0.5 bg-amber-500/20 text-amber-600 border-amber-500/30">
              <Zap size={12} />
              YOLO
            </Badge>
          )}
          {/* Pickup paused badge */}
          {pickupPaused && !gracefulShutdown && (
            <Badge variant="outline" className="gap-1 text-xs py-0.5 border-amber-500 text-amber-600">
              <PauseCircle size={12} />
              Paused
            </Badge>
          )}
          {/* Graceful shutdown badge */}
          {gracefulShutdown && (
            <Badge variant="outline" className="gap-1 text-xs py-0.5 border-orange-500 text-orange-600">
              <AlertTriangle size={12} />
              Stopping
            </Badge>
          )}
          {/* Connection status badge */}
          <Badge variant={isConnected ? 'default' : 'destructive'} className="gap-1 text-xs py-0.5">
            {isConnected ? (
              <>
                <Wifi size={12} />
                Live
              </>
            ) : (
              <>
                <WifiOff size={12} />
                Offline
              </>
            )}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="pb-3">
        {/* Compact horizontal layout */}
        <div className="flex items-center gap-4">
          {/* Percentage */}
          <div className="flex items-baseline">
            <span className="text-4xl font-bold tabular-nums">
              {percentage.toFixed(1)}
            </span>
            <span className="text-xl font-semibold text-muted-foreground">
              %
            </span>
          </div>

          {/* Progress Bar - grows to fill space */}
          <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-primary rounded-full transition-all duration-500 ease-out"
              style={{ width: `${percentage}%` }}
            />
          </div>

          {/* Stats */}
          <div className="flex items-center gap-2 text-center shrink-0">
            <span className="font-mono text-xl font-bold text-primary">
              {passing}
            </span>
            <span className="text-lg text-muted-foreground">/</span>
            <span className="font-mono text-xl font-bold">
              {total}
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
