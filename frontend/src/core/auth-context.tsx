import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuthStore } from '../features/auth/store'

interface ProtectedRouteProps {
  readonly children: ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps): JSX.Element {
  const accessToken = useAuthStore((s) => s.accessToken)

  if (!accessToken) {
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
