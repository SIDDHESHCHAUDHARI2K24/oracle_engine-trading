import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { TicketListResponse } from '../../../core/types'

export const ticketKeys = {
  all: ['tickets'] as const,
  lists: (filters: Record<string, string | number | undefined>) =>
    [...ticketKeys.all, 'list', filters] as const,
  details: () => [...ticketKeys.all, 'detail'] as const,
  detail: (id: string) => [...ticketKeys.details(), id] as const,
  history: (filters: Record<string, string | number | undefined>) =>
    [...ticketKeys.all, 'history', filters] as const,
}

export function useTickets(
  universeId?: string,
  horizon?: string,
  minConviction?: number,
  minPasses?: number,
  limit = 100,
  offset = 0,
): UseQueryResult<TicketListResponse> {
  const params = new URLSearchParams()
  if (universeId) params.set('universe_id', universeId)
  if (horizon) params.set('horizon', horizon)
  if (minConviction !== undefined && minConviction > 0) params.set('min_conviction', String(minConviction))
  if (minPasses !== undefined && minPasses > 0) params.set('min_passes', String(minPasses))
  params.set('limit', String(limit))
  params.set('offset', String(offset))
  const qs = params.toString()

  return useQuery({
    queryKey: ticketKeys.lists({ universeId, horizon, minConviction, minPasses, limit, offset }),
    queryFn: () => apiClient.get<TicketListResponse>(`/api/v1/tickets?${qs}`),
    refetchInterval: 60_000,
  })
}
