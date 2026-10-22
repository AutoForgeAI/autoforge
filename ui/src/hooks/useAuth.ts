/**
 * Auth hooks: who is signed in and what they may do.
 *
 * When server-side auth is disabled (the default), every helper reports full
 * access so the UI behaves exactly as before.
 */

import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import * as api from '../lib/api'
import type { AuthMe, ProjectRole } from '../lib/types'

export function useAuthMe() {
  const queryClient = useQueryClient()

  // Re-check the session whenever an API call comes back 401
  useEffect(() => {
    const onUnauthorized = () => queryClient.invalidateQueries({ queryKey: ['auth-me'] })
    window.addEventListener(api.UNAUTHORIZED_EVENT, onUnauthorized)
    return () => window.removeEventListener(api.UNAUTHORIZED_EVENT, onUnauthorized)
  }, [queryClient])

  return useQuery({
    queryKey: ['auth-me'],
    queryFn: api.getAuthMe,
    staleTime: 60_000,
    retry: 1,
  })
}

export function useLogout() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: api.logout,
    onSuccess: (result) => {
      if (result.logout_url) {
        window.location.href = result.logout_url
        return
      }
      queryClient.clear()
      queryClient.invalidateQueries({ queryKey: ['auth-me'] })
    },
  })
}

export interface Permissions {
  authEnabled: boolean
  isAdmin: boolean
  role: ProjectRole
  canWrite: boolean
  readOnly: boolean
}

export function permissionsFor(me: AuthMe | undefined, projectName: string | null): Permissions {
  if (!me?.enabled) {
    return { authEnabled: false, isAdmin: true, role: 'developer', canWrite: true, readOnly: false }
  }
  const role: ProjectRole = me.is_admin
    ? 'developer'
    : (projectName && me.project_roles[projectName]) || 'none'
  return {
    authEnabled: true,
    isAdmin: me.is_admin,
    role,
    canWrite: role === 'developer',
    readOnly: role === 'readonly',
  }
}

/** Permissions of the signed-in user, optionally for a specific project. */
export function usePermissions(projectName: string | null = null): Permissions {
  const { data } = useAuthMe()
  return permissionsFor(data, projectName)
}
