import { Routes, Route, Navigate } from 'react-router-dom'
import { LoginPage } from './features/auth/pages/LoginPage'
import { UniverseListPage } from './features/universes/pages/UniverseListPage'
import { ProtectedRoute } from './core/auth-context'

export default function App(): JSX.Element {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/universes"
        element={
          <ProtectedRoute>
            <UniverseListPage />
          </ProtectedRoute>
        }
      />
      <Route path="/" element={<Navigate to="/universes" replace />} />
      <Route path="*" element={<Navigate to="/universes" replace />} />
    </Routes>
  )
}
