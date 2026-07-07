import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { IngestionTriggerResponse } from '../../../core/types'
import { monitoringKeys } from './useIngestStatus'

interface TriggerVariables {
  readonly mode?: string
}

export function useTriggerIngestion(): UseMutationResult<
  IngestionTriggerResponse,
  Error,
  TriggerVariables
> {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (vars) =>
      apiClient.post<IngestionTriggerResponse>('/api/v1/data_ingestion/trigger', vars),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: monitoringKeys.ingestStatus() })
    },
  })
}
