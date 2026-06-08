import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { AddResult } from '../../../core/types'

export function useAddMembers(
  universeId: string,
): UseMutationResult<AddResult, Error, readonly string[]> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (symbols) =>
      apiClient.post<AddResult>(`/api/v1/universes/${universeId}/membership`, { symbols }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['universes', universeId] })
    },
  })
}
