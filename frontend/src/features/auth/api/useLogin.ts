import { useMutation, type UseMutationResult } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { apiClient } from '../../../core/api-client'
import { useAuthStore } from '../store'
import type { TokenResponse } from '../../../core/types'

interface LoginCredentials {
  readonly email: string
  readonly password: string
}

export function useLogin(): UseMutationResult<TokenResponse, Error, LoginCredentials> {
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)

  return useMutation({
    mutationFn: (creds: LoginCredentials) =>
      apiClient.post<TokenResponse>('/auth/login', creds),
    onSuccess: (data) => {
      setAuth(data.access_token, data.user)
      void navigate('/universes')
    },
  })
}
