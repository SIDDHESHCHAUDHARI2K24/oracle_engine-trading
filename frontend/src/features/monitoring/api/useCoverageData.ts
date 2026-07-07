import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { CoverageEntry } from '../../../core/types'
import { monitoringKeys } from './monitoringKeys'

export function useCoverageData(
  universeId: string,
  horizon: string,
  windowSize = 90,
): UseQueryResult<readonly CoverageEntry[]> {
  const params = new URLSearchParams()
  params.set('universe_id', universeId)
  params.set('horizon', horizon)
  params.set('window_size', String(windowSize))
  const qs = params.toString()

  return useQuery({
    queryKey: monitoringKeys.coverage({ universeId, horizon, windowSize }),
    queryFn: () => apiClient.get<readonly CoverageEntry[]>(`/api/v1/monitoring/coverage?${qs}`),
    enabled: universeId.length > 0 && horizon.length > 0,
    refetchInterval: 60_000,
  })
}
