import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { TickerSummary } from '../../../core/types'

export function useMembership(
  universeId: string,
  atDate?: string,
): UseQueryResult<readonly TickerSummary[]> {
  return useQuery({
    queryKey: ['universes', universeId, 'membership', atDate ?? 'current'],
    queryFn: () => {
      const params = atDate ? `?at=${atDate}` : ''
      return apiClient.get<readonly TickerSummary[]>(
        `/api/v1/universes/${universeId}/membership${params}`,
      )
    },
    enabled: !!universeId,
  })
}
