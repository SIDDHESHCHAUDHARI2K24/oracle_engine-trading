import { create } from 'zustand'
import type { UserResponse } from '../../core/types'

interface AuthState {
  readonly accessToken: string | null
  readonly user: UserResponse | null
  setAuth: (token: string, user: UserResponse) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>((set) => ({
  accessToken: null,
  user: null,
  setAuth: (token, user) => set({ accessToken: token, user }),
  logout: () => set({ accessToken: null, user: null }),
}))
