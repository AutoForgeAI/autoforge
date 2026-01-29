/**
 * React Query hooks for settings management
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import * as api from '../lib/api'
import type { ModelConfig } from '../lib/types'

// ============================================================================
// App Settings
// ============================================================================

export function useAppSettings() {
  return useQuery({
    queryKey: ['app-settings'],
    queryFn: api.getAppSettings,
    staleTime: 60000, // Cache for 1 minute
  })
}

export function useUpdateAppSettings() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (models: ModelConfig) => api.updateAppSettings(models),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['app-settings'] })
      // Also invalidate project settings since they may inherit from app
      queryClient.invalidateQueries({ queryKey: ['project-settings'] })
      queryClient.invalidateQueries({ queryKey: ['merged-settings'] })
    },
  })
}

export function useAvailableModels() {
  return useQuery({
    queryKey: ['available-models'],
    queryFn: api.getAvailableModels,
    staleTime: 300000, // Cache for 5 minutes (models don't change often)
  })
}

// ============================================================================
// Project Settings
// ============================================================================

export function useProjectSettings(projectName: string | null) {
  return useQuery({
    queryKey: ['project-settings', projectName],
    queryFn: () => api.getProjectSettings(projectName!),
    enabled: !!projectName,
    staleTime: 30000, // Cache for 30 seconds
  })
}

export function useUpdateProjectSettings(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (models: ModelConfig) => api.updateProjectSettings(projectName, models),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project-settings', projectName] })
      queryClient.invalidateQueries({ queryKey: ['merged-settings', projectName] })
    },
  })
}

export function useDeleteProjectSettings(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => api.deleteProjectSettings(projectName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project-settings', projectName] })
      queryClient.invalidateQueries({ queryKey: ['merged-settings', projectName] })
    },
  })
}

// ============================================================================
// Merged Settings
// ============================================================================

export function useMergedSettings(projectName: string | null) {
  return useQuery({
    queryKey: ['merged-settings', projectName],
    queryFn: () => api.getMergedSettings(projectName!),
    enabled: !!projectName,
    staleTime: 30000, // Cache for 30 seconds
  })
}
