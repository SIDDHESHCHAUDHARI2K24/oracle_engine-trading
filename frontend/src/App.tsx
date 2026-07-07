import { Routes, Route, Navigate } from 'react-router-dom'
import { LoginPage } from './features/auth/pages/LoginPage'
import { AccountSettingsPage } from './features/auth/pages/AccountSettingsPage'
import { UniverseListPage } from './features/universes/pages/UniverseListPage'
import { UniverseDetailPage } from './features/universes/pages/UniverseDetailPage'
import { UniverseFormPage } from './features/universes/pages/UniverseFormPage'
import { MonitoringPage } from './features/monitoring/pages/MonitoringPage'
import { ModelCardPage } from './features/monitoring/pages/ModelCardPage'
import { AlertsPage } from './features/monitoring/pages/AlertsPage'
import { PipelineRunsPage } from './features/monitoring/pages/PipelineRunsPage'
import { AlertsBanner } from './features/monitoring/components/AlertsBanner'
import { InboxPage } from './features/conviction_tickets/pages/InboxPage'
import { DetailPage as TicketDetailPage } from './features/conviction_tickets/pages/DetailPage'
import { HistoryPage } from './features/conviction_tickets/pages/HistoryPage'
import { ExplorerPage as BacktestExplorerPage } from './features/backtesting/pages/ExplorerPage'
import { TickerDetailPage } from './features/backtesting/pages/TickerDetailPage'
import { ProtectedRoute } from './core/auth-context'

export default function App(): JSX.Element {
  return (
    <>
      <AlertsBanner />
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
      <Route
        path="/monitoring/:universeId"
        element={
          <ProtectedRoute>
            <ModelCardPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/monitoring"
        element={
          <ProtectedRoute>
            <MonitoringPage />
          </ProtectedRoute>
        }
      />
        <Route
          path="/monitoring/alerts"
          element={
            <ProtectedRoute>
              <AlertsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/monitoring/runs"
          element={
            <ProtectedRoute>
              <PipelineRunsPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tickets"
          element={
            <ProtectedRoute>
              <InboxPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tickets/history"
          element={
            <ProtectedRoute>
              <HistoryPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tickets/:id"
          element={
            <ProtectedRoute>
              <TicketDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/backtests/:universeId"
          element={
            <ProtectedRoute>
              <BacktestExplorerPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/backtests/:universeId/:tickerId"
          element={
            <ProtectedRoute>
              <TickerDetailPage />
            </ProtectedRoute>
          }
        />
        <Route path="/" element={<Navigate to="/universes" replace />} />
        <Route path="*" element={<Navigate to="/universes" replace />} />
      </Routes>
    </>
  )
}
