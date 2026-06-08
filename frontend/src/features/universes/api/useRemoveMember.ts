import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'

export function useRemoveMember(
  universeId: string,
): UseMutationResult<{ detail: string }, Error, string> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (tickerId) =>
      apiClient.delete<{ detail: string }>(
        `/api/v1/universes/${universeId}/membership/${tickerId}`,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['universes', universeId] })
    },
  })
}
