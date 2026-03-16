import { AlertCircle, LogIn, X } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'

interface AuthenticationAlertProps {
  isOpen: boolean
  onClose: () => void
  message: string
  onLogin?: () => void
}

export function AuthenticationAlert({ 
  isOpen, 
  onClose, 
  message, 
  onLogin 
}: AuthenticationAlertProps) {
  if (!isOpen) return null

  return (
    <div className="fixed top-4 right-4 z-50 max-w-md animate-in slide-in-from-right">
      <Alert variant="destructive" className="border-red-200 bg-red-50 dark:bg-red-950/20">
        <AlertCircle className="h-4 w-4 text-red-600 dark:text-red-400" />
        <div className="flex-1">
          <AlertDescription className="text-red-800 dark:text-red-200 font-medium">
            {message}
          </AlertDescription>
          {onLogin && (
            <div className="mt-2 flex gap-2">
              <Button 
                size="sm" 
                variant="destructive"
                onClick={onLogin}
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                <LogIn className="h-3 w-3 mr-1" />
                Login to Claude
              </Button>
              <Button 
                size="sm" 
                variant="outline"
                onClick={onClose}
                className="border-red-200 text-red-700 hover:bg-red-100"
              >
                Dismiss
              </Button>
            </div>
          )}
        </div>
        {!onLogin && (
          <Button
            size="sm"
            variant="ghost"
            onClick={onClose}
            className="h-6 w-6 p-0 text-red-600 hover:text-red-700 hover:bg-red-100"
          >
            <X className="h-3 w-3" />
          </Button>
        )}
      </Alert>
    </div>
  )
}

interface UsageLimitAlertProps {
  isOpen: boolean
  onClose: () => void
  resetTime: string
  waitSeconds: number
}

export function UsageLimitAlert({ 
  isOpen, 
  onClose, 
  resetTime, 
  waitSeconds 
}: UsageLimitAlertProps) {
  if (!isOpen) return null

  const formatWaitTime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    if (hours > 0) {
      return `${hours}h ${minutes}m`
    }
    return `${minutes}m`
  }

  return (
    <div className="fixed top-4 right-4 z-50 max-w-md animate-in slide-in-from-right">
      <Alert variant="default" className="border-orange-200 bg-orange-50 dark:bg-orange-950/20">
        <AlertCircle className="h-4 w-4 text-orange-600 dark:text-orange-400" />
        <div className="flex-1">
          <AlertDescription className="text-orange-800 dark:text-orange-200 font-medium">
            Claude usage limit reached. AutoForge will automatically resume at {resetTime}.
          </AlertDescription>
          <div className="mt-1 text-sm text-orange-700 dark:text-orange-300">
            Waiting approximately {formatWaitTime(waitSeconds)}...
          </div>
        </div>
        <Button
          size="sm"
          variant="ghost"
          onClick={onClose}
          className="h-6 w-6 p-0 text-orange-600 hover:text-orange-700 hover:bg-orange-100"
        >
          <X className="h-3 w-3" />
        </Button>
      </Alert>
    </div>
  )
}
