import type { ReactNode } from 'react'
import { Loader2, LogIn, LogOut, ShieldAlert } from 'lucide-react'
import { useAuthMe, useLogout } from '../hooks/useAuth'
import { loginUrl } from '../lib/api'
import type { AuthMe } from '../lib/types'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'

/**
 * Renders the app only once the user may use it.
 *
 * With server auth disabled this is a pass-through. With OIDC enabled it shows
 * a sign-in screen until a session exists, and a "no access" screen for
 * signed-in users who have not been granted any role yet.
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const { data: me, isLoading } = useAuthMe()

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 size={32} className="animate-spin text-primary" />
      </div>
    )
  }

  // If /api/auth/me fails, fall through: the API still enforces access.
  if (!me?.enabled) return <>{children}</>
  if (!me.authenticated) return <LoginScreen providerName={me.provider_name} />
  if (!hasAnyAccess(me)) return <NoAccessScreen me={me} />
  return <>{children}</>
}

function hasAnyAccess(me: AuthMe): boolean {
  return me.is_admin || Object.values(me.project_roles).some(role => role !== 'none')
}

function GateCard({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <Card className="w-full max-w-md">
        <CardContent className="p-8 flex flex-col items-center text-center gap-4">
          <img src="/logo.png" alt="AutoForge" className="h-12 w-12 rounded-full" />
          {children}
        </CardContent>
      </Card>
    </div>
  )
}

function LoginScreen({ providerName }: { providerName: string | null }) {
  return (
    <GateCard>
      <h1 className="font-display text-2xl font-bold">Sign in to AutoForge</h1>
      <p className="text-sm text-muted-foreground">
        This AutoForge server requires you to sign in before using it.
      </p>
      <Button asChild className="w-full mt-2">
        <a href={loginUrl()}>
          <LogIn size={16} />
          Sign in with {providerName || 'SSO'}
        </a>
      </Button>
    </GateCard>
  )
}

function NoAccessScreen({ me }: { me: AuthMe }) {
  const logout = useLogout()
  const user = me.user

  return (
    <GateCard>
      <ShieldAlert size={32} className="text-yellow-500" />
      <h1 className="font-display text-2xl font-bold">No access yet</h1>
      <p className="text-sm text-muted-foreground">
        You are signed in, but you have not been given a role on any project.
        Ask an AutoForge admin to add you to <code className="font-mono">auth.yaml</code>.
      </p>
      {user && (
        <div className="w-full text-left text-xs bg-muted rounded-md p-3 space-y-1 font-mono break-all">
          <div>user: {user.email || user.username || user.sub}</div>
          <div>groups: {user.groups.length > 0 ? user.groups.join(', ') : '(none)'}</div>
        </div>
      )}
      <Button variant="outline" className="w-full" onClick={() => logout.mutate()} disabled={logout.isPending}>
        <LogOut size={16} />
        Sign out
      </Button>
    </GateCard>
  )
}
