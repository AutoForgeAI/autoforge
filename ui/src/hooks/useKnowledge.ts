/**
 * React Query hooks for project knowledge documents
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import * as api from '../lib/api'

/**
 * Hook to list a project's knowledge documents.
 */
export function useKnowledgeFiles(projectName: string | null) {
  return useQuery({
    queryKey: ['knowledge', projectName],
    queryFn: () => api.listKnowledgeFiles(projectName!),
    enabled: !!projectName,
  })
}

/**
 * Hook to fetch a single knowledge document's content.
 */
export function useKnowledgeFile(projectName: string | null, filename: string | null) {
  return useQuery({
    queryKey: ['knowledge', projectName, filename],
    queryFn: () => api.getKnowledgeFile(projectName!, filename!),
    enabled: !!projectName && !!filename,
  })
}

/**
 * Hook to upload (create or overwrite) a knowledge document.
 */
export function useUploadKnowledgeFile(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ filename, content }: { filename: string; content: string }) =>
      api.uploadKnowledgeFile(projectName, filename, content),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge', projectName] })
    },
  })
}

/**
 * Hook to delete a knowledge document.
 */
export function useDeleteKnowledgeFile(projectName: string) {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (filename: string) => api.deleteKnowledgeFile(projectName, filename),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['knowledge', projectName] })
    },
  })
}
