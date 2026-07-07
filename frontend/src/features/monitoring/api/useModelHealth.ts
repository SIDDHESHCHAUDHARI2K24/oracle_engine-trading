import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { ModelHealthSummary } from '../../../core/types'
import { monitoringKeys } from './monitoringKeys'

export function useModelHealth(): UseQueryResult<readonly ModelHealthSummary[]> {
  return useQuery({
    queryKey: monitoringKeys.modelHealth(),
    queryFn: () => apiClient.get<readonly ModelHealthSummary[]>('/api/v1/monitoring/health'),
    refetchInterval: 60_000,
  })
}
