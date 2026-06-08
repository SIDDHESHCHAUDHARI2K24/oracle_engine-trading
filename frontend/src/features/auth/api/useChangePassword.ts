import { useMutation, type UseMutationResult } from '@tanstack/react-query'
import { apiClient } from '../../../core/api-client'

interface ChangePasswordVariables {
  readonly old_password: string
  readonly new_password: string
}

export function useChangePassword(): UseMutationResult<
  { detail: string },
  Error,
  ChangePasswordVariables
> {
  return useMutation({
    mutationFn: (vars: ChangePasswordVariables) =>
      apiClient.post<{ detail: string }>('/api/v1/auth/change-password', vars),
  })
}
