import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { ModelCardDetail } from '../../../core/types'
import { monitoringKeys } from './monitoringKeys'

export function useModelCard(universeId: string): UseQueryResult<ModelCardDetail> {
  return useQuery({
    queryKey: monitoringKeys.modelCard(universeId),
    queryFn: () => apiClient.get<ModelCardDetail>(`/api/v1/monitoring/health/${universeId}`),
    enabled: universeId.length > 0,
    refetchInterval: 60_000,
  })
}
