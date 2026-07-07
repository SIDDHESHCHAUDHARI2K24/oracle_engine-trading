import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { AlertsListResponse, AlertSeverity } from '../../../core/types'

export const alertKeys = {
  all: ['alerts'] as const,
  lists: (filters: Record<string, string | undefined>) =>
    [...alertKeys.all, 'list', filters] as const,
}

export function useSystemAlerts(filters?: {
  severity?: AlertSeverity
  universe_id?: string
}): UseQueryResult<AlertsListResponse> {
  const params = new URLSearchParams()
  if (filters?.severity) params.set('severity', filters.severity)
  if (filters?.universe_id) params.set('universe_id', filters.universe_id)
  const qs = params.toString()

  return useQuery({
    queryKey: alertKeys.lists({
      severity: filters?.severity,
      universeId: filters?.universe_id,
    }),
    queryFn: () =>
      apiClient.get<AlertsListResponse>(
        `/api/v1/monitoring/alerts${qs ? `?${qs}` : ''}`,
      ),
    refetchInterval: 60_000,
  })
}
