import { Routes, Route, Navigate } from 'react-router-dom'
import { LoginPage } from './features/auth/pages/LoginPage'
import { AccountSettingsPage } from './features/auth/pages/AccountSettingsPage'
import { UniverseListPage } from './features/universes/pages/UniverseListPage'
import { UniverseDetailPage } from './features/universes/pages/UniverseDetailPage'
import { UniverseFormPage } from './features/universes/pages/UniverseFormPage'
import { ProtectedRoute } from './core/auth-context'

export default function App(): JSX.Element {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/settings/account"
        element={
          <ProtectedRoute>
            <AccountSettingsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/universes/new"
        element={
          <ProtectedRoute>
            <UniverseFormPage mode="create" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/universes/:id/edit"
        element={
          <ProtectedRoute>
            <UniverseFormPage mode="edit" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/universes/:id"
        element={
          <ProtectedRoute>
            <UniverseDetailPage />
          </ProtectedRoute>
        }
      />
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
