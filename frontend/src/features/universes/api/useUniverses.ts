import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { UniverseListResponse } from '../../../core/types'

export const universeKeys = {
  all: ['universes'] as const,
  lists: (includeDeleted = false) => [...universeKeys.all, 'list', { includeDeleted }] as const,
  details: () => [...universeKeys.all, 'detail'] as const,
  detail: (id: string) => [...universeKeys.details(), id] as const,
}

export function useUniverses(includeDeleted = false): UseQueryResult<UniverseListResponse> {
  return useQuery({
    queryKey: universeKeys.lists(includeDeleted),
    queryFn: () => {
      const params = includeDeleted ? '?include_deleted=true' : ''
      return apiClient.get<UniverseListResponse>(`/api/v1/universes${params}`)
    },
  })
}
