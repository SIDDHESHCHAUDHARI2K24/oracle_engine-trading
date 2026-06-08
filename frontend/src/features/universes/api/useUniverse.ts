import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { UniverseDetail } from '../../../core/types'

export function useUniverse(id: string): UseQueryResult<UniverseDetail> {
  return useQuery({
    queryKey: ['universes', id],
    queryFn: () => apiClient.get<UniverseDetail>(`/api/v1/universes/${id}`),
    enabled: !!id,
  })
}
