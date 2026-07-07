import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { IngestionStatusResponse } from '../../../core/types'
import { monitoringKeys } from './monitoringKeys'

export function useIngestStatus(): UseQueryResult<IngestionStatusResponse> {
  return useQuery({
    queryKey: monitoringKeys.ingestStatus(),
    queryFn: () => apiClient.get<IngestionStatusResponse>('/api/v1/data_ingestion/status'),
    refetchInterval: 60_000,
  })
}
