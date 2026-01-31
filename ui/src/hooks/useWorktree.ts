/**
 * React Query hooks for git worktree operations
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getWorktreeStatus,
  getWorktreeDiff,
  createWorktree,
  mergeWorktree,
  stageWorktreeChanges,
  discardWorktree,
} from '../lib/api'

/**
 * Hook to get the worktree status for a project
 */
export function useWorktreeStatus(projectName: string) {
  return useQuery({
    queryKey: ['worktree-status', projectName],
    queryFn: () => getWorktreeStatus(projectName),
    refetchInterval: 10000, // Refresh every 10 seconds
    enabled: !!projectName,
  })
}

/**
 * Hook to get the worktree diff
 */
export function useWorktreeDiff(projectName: string, enabled = true) {
  return useQuery({
    queryKey: ['worktree-diff', projectName],
    queryFn: () => getWorktreeDiff(projectName),
    enabled: !!projectName && enabled,
  })
}

/**
 * Hook to create a worktree
 */
export function useCreateWorktree(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (fromBranch?: string) => createWorktree(projectName, fromBranch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['worktree-status', projectName] })
    },
  })
}

/**
 * Hook to merge worktree changes to main branch
 */
export function useMergeWorktree(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ commitMessage, deleteAfter = true }: { commitMessage?: string; deleteAfter?: boolean }) =>
      mergeWorktree(projectName, commitMessage, deleteAfter),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['worktree-status', projectName] })
      queryClient.invalidateQueries({ queryKey: ['worktree-diff', projectName] })
      queryClient.invalidateQueries({ queryKey: ['git-status', projectName] })
    },
  })
}

/**
 * Hook to stage worktree changes without committing
 */
export function useStageWorktreeChanges(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => stageWorktreeChanges(projectName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['worktree-status', projectName] })
      queryClient.invalidateQueries({ queryKey: ['git-status', projectName] })
    },
  })
}

/**
 * Hook to discard worktree changes
 */
export function useDiscardWorktree(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () => discardWorktree(projectName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['worktree-status', projectName] })
      queryClient.invalidateQueries({ queryKey: ['worktree-diff', projectName] })
    },
  })
}
