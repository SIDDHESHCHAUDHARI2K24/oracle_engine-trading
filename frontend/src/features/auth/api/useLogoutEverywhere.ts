import { useMutation, type UseMutationResult } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../../../core/api-client'
import { useAuthStore } from '../store'

export function useLogoutEverywhere(): UseMutationResult<
  { detail: string },
  Error,
  void
> {
  const navigate = useNavigate()

  return useMutation({
    mutationFn: () =>
      apiClient.post<{ detail: string }>('/api/v1/auth/logout-everywhere'),
    onSuccess: () => {
      useAuthStore.getState().logout()
      void navigate('/login')
    },
  })
}
