import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getGsdStatus, gsdToSpec } from '../lib/api'

export function useGsdStatus(projectName: string) {
  return useQuery({
    queryKey: ['gsd-status', projectName],
    queryFn: () => getGsdStatus(projectName),
    staleTime: 5_000,
  })
}

export function useGsdToSpec(projectName: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: Parameters<typeof gsdToSpec>[1]) => gsdToSpec(projectName, req),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['gsd-status', projectName] })
    },
  })
}

