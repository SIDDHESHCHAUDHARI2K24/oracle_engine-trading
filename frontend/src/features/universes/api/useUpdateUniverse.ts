import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { UniverseDetail } from '../../../core/types'

interface UpdateUniverseVariables {
  readonly name?: string
  readonly display_name?: string
  readonly description?: string
}

export function useUpdateUniverse(
  id: string,
): UseMutationResult<UniverseDetail, Error, UpdateUniverseVariables> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (vars) => apiClient.patch<UniverseDetail>(`/api/v1/universes/${id}`, vars),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['universes'] })
    },
  })
}
