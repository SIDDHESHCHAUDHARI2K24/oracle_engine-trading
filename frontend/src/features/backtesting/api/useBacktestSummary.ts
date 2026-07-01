import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { UniversePassSummary } from '../../../core/types'

export const backtestKeys = {
  all: ['backtests'] as const,
  universe: (universeId: string) => [...backtestKeys.all, 'universe', universeId] as const,
  detail: (universeId: string, tickerId: string) =>
    [...backtestKeys.all, 'detail', universeId, tickerId] as const,
}

export function useBacktestSummary(
  universeId: string,
): UseQueryResult<UniversePassSummary> {
  return useQuery({
    queryKey: backtestKeys.universe(universeId),
    queryFn: () =>
      apiClient.get<UniversePassSummary>(`/api/v1/backtests/${universeId}`),
    enabled: !!universeId,
  })
}
