import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { UniverseListResponse } from '../../../core/types'

const universeKeys = {
  all: ['universes'] as const,
  lists: () => [...universeKeys.all, 'list'] as const,
}

export function useUniverses(): UseQueryResult<UniverseListResponse> {
  return useQuery({
    queryKey: universeKeys.lists(),
    queryFn: () => apiClient.get<UniverseListResponse>('/api/v1/universes'),
  })
}
