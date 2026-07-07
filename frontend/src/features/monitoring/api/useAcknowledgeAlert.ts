import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { AlertActionResponse } from '../../../core/types'
import { alertKeys } from './useSystemAlerts'

export function useAcknowledgeAlert(
  alertId: string,
): UseMutationResult<AlertActionResponse, Error, void> {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: () =>
      apiClient.post<AlertActionResponse>(
        `/api/v1/monitoring/alerts/${alertId}/acknowledge`,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: alertKeys.all })
    },
  })
}
