import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import { backtestKeys } from './useBacktestSummary'
import type { TickerBacktestDetail } from '../../../core/types'

export function useBacktestDetail(
  universeId: string,
  tickerId: string,
): UseQueryResult<TickerBacktestDetail> {
  return useQuery({
    queryKey: backtestKeys.detail(universeId, tickerId),
    queryFn: () =>
      apiClient.get<TickerBacktestDetail>(`/api/v1/backtests/${universeId}/${tickerId}`),
    enabled: !!universeId && !!tickerId,
  })
}
