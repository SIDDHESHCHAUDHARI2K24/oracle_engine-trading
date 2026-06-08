import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { UniverseDetail } from '../../../core/types'

interface CreateUniverseVariables {
  readonly name: string
  readonly display_name: string
  readonly description?: string
}

export function useCreateUniverse(): UseMutationResult<UniverseDetail, Error, CreateUniverseVariables> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars) => apiClient.post<UniverseDetail>('/api/v1/universes', vars),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['universes'] })
    },
  })
}
