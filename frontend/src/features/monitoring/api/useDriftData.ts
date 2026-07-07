import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { DriftData } from '../../../core/types'
import { monitoringKeys } from './monitoringKeys'

export function useDriftData(universeId: string): UseQueryResult<DriftData> {
  return useQuery({
    queryKey: monitoringKeys.drift(universeId),
    queryFn: () => apiClient.get<DriftData>(`/api/v1/monitoring/drift?universe_id=${universeId}`),
    enabled: universeId.length > 0,
    refetchInterval: 60_000,
  })
}
