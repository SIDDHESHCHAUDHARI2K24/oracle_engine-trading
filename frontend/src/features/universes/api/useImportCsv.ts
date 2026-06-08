import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'
import { ApiRequestError } from '../../../core/api-client'
import { useAuthStore } from '../../auth/store'
import type { ImportResult } from '../../../core/types'

const API_BASE = import.meta.env['VITE_API_BASE_URL'] ?? 'http://127.0.0.1:8000'

export function useImportCsv(
  universeId: string,
): UseMutationResult<ImportResult, Error, File> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      const token = useAuthStore.getState().accessToken
      const res = await fetch(
        `${API_BASE}/api/v1/universes/${universeId}/membership/import`,
        {
          method: 'POST',
          credentials: 'include',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: formData,
        },
      )
      if (!res.ok) {
        const err = await res.json().catch(() => ({
          error_code: 'UNKNOWN',
          message: 'Upload failed',
        }))
        throw new ApiRequestError(err.error_code, err.message, err.details)
      }
      return res.json() as Promise<ImportResult>
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['universes', universeId] })
    },
  })
}
