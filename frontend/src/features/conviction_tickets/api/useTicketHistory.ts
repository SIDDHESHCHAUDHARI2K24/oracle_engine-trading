import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import { ticketKeys } from './useTickets'
import type { TicketListResponse } from '../../../core/types'

export function useTicketHistory(
  status?: string,
  outcome?: string,
  limit = 100,
  offset = 0,
): UseQueryResult<TicketListResponse> {
  const params = new URLSearchParams()
  if (status) params.set('status', status)
  if (outcome) params.set('outcome', outcome)
  params.set('limit', String(limit))
  params.set('offset', String(offset))
  const qs = params.toString()

  return useQuery({
    queryKey: ticketKeys.history({ status, outcome, limit, offset }),
    queryFn: () => apiClient.get<TicketListResponse>(`/api/v1/tickets/history?${qs}`),
  })
}
