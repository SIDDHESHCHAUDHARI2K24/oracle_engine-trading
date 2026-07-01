import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { ConvictionTicket } from '../../../core/types'

export function useTicket(id: string): UseQueryResult<ConvictionTicket> {
  return useQuery({
    queryKey: ['tickets', id],
    queryFn: () => apiClient.get<ConvictionTicket>(`/api/v1/tickets/${id}`),
    enabled: !!id,
  })
}
