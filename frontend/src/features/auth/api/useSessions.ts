import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'
import type { SessionInfo } from '../../../core/types'

export function useSessions(): UseQueryResult<SessionInfo[]> {
  return useQuery({
    queryKey: ['auth', 'sessions'],
    queryFn: () => apiClient.get<SessionInfo[]>('/api/v1/auth/sessions'),
    refetchInterval: 60_000,
  })
}
