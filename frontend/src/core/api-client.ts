import { useAuthStore } from '../features/auth/store'
import type { ApiError } from './types'

const API_BASE = import.meta.env['VITE_API_BASE_URL'] ?? 'http://127.0.0.1:8000'

export class ApiRequestError extends Error {
  public readonly code: string
  public readonly details: Record<string, unknown> | undefined

  constructor(code: string, message: string, details?: Record<string, unknown>) {
    super(message)
    this.name = 'ApiRequestError'
    this.code = code
    this.details = details
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.status === 401) {
    useAuthStore.getState().logout()
    window.location.href = '/login'
    throw new ApiRequestError('SESSION_EXPIRED', 'Session expired. Please log in again.')
  }
  if (!res.ok) {
    const err: ApiError = await res.json().catch(() => ({
      error_code: 'UNKNOWN_ERROR',
      message: 'An unexpected error occurred',
    }))
    throw new ApiRequestError(err.error_code, err.message, err.details)
  }
  return res.json() as Promise<T>
}

function getAuthHeader(): Record<string, string> {
  const token = useAuthStore.getState().accessToken
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export const apiClient = {
  async get<T>(path: string): Promise<T> {
    const res = await fetch(`${API_BASE}${path}`, {
      credentials: 'include',
      headers: { ...getAuthHeader() },
    })
    return handleResponse<T>(res)
  },

  async post<T>(path: string, body?: unknown): Promise<T> {
    const res = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...getAuthHeader() },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
    return handleResponse<T>(res)
  },
}
