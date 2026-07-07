import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { AlertActionResponse } from '../../../core/types'
import { alertKeys } from './useSystemAlerts'

export function useResolveAlert(
  alertId: string,
): UseMutationResult<AlertActionResponse, Error, void> {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () =>
      apiClient.post<AlertActionResponse>(
        `/api/v1/monitoring/alerts/${alertId}/resolve`,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: alertKeys.all })
    },
  })
}
