import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { IngestionStatusPanel } from '../components/IngestionStatusPanel'
import { HealthBadge } from '../components/HealthBadge'
import { CorrelationChart } from '../components/CorrelationChart'
import { useModelHealth } from '../api/useModelHealth'
import { Card, CardContent } from '../../../shared/components/ui/card'
import { Button } from '../../../shared/components/ui/button'
import { CoveragePage } from './CoveragePage'
import { DriftPage } from './DriftPage'

type TabId = 'overview' | 'coverage' | 'drift' | 'runs'

const TABS: readonly { readonly id: TabId; readonly label: string }[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'coverage', label: 'Coverage' },
  { id: 'drift', label: 'Drift' },
  { id: 'runs', label: 'Runs' },
]

export function MonitoringPage(): JSX.Element {
  const [tab, setTab] = useState<TabId>('overview')

  return (
    <main className="mx-auto max-w-6xl p-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Pipeline Monitoring</h1>
        <p className="text-muted-foreground mt-1">
          Data ingestion status, model health, and drift analysis.
        </p>
      </div>

      <div className="mb-6 flex gap-1 rounded-lg border bg-muted p-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`flex-1 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
              tab === t.id
                ? 'bg-white text-foreground shadow-sm'
                : 'text-muted-foreground hover:text-foreground'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'overview' && <OverviewTab />}
      {tab === 'coverage' && <CoveragePage />}
      {tab === 'drift' && <DriftPage />}
      {tab === 'runs' && <RunsTab />}
    </main>
  )
}

function OverviewTab(): JSX.Element {
  const navigate = useNavigate()
  const { data, isLoading, isError, error, refetch } = useModelHealth()

  return (
    <div className="space-y-6">
      <IngestionStatusPanel />

      {isLoading && (
        <Card>
          <CardContent className="flex flex-col gap-3 py-12">
            <div className="mx-auto h-4 w-1/3 animate-pulse rounded bg-gray-200" />
            <div className="mx-auto h-4 w-1/4 animate-pulse rounded bg-gray-200" />
          </CardContent>
        </Card>
      )}

      {isError && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-red-600" role="alert">
              {error instanceof Error ? error.message : 'Failed to load model health'}
            </p>
            <Button type="button" variant="outline" className="mt-4" onClick={() => refetch()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {data && !isLoading && !isError && data.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">No universes configured.</p>
          </CardContent>
        </Card>
      )}

      {data && data.length > 0 && !isLoading && !isError && (
        <>
          <CorrelationChart
            data={data.map((d) => ({
              universe_id: d.universe_id,
              universe_name: d.universe_name,
              conviction_correlation: d.conviction_correlation,
            }))}
          />

          <h2 className="text-lg font-semibold">Universe Health</h2>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {data.map((u) => (
              <Card
                key={u.universe_id}
                className="cursor-pointer transition-shadow hover:shadow-md"
                onClick={() => navigate(`/monitoring/${u.universe_id}`)}
              >
                <CardContent className="space-y-3 py-5">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold">{u.universe_name}</span>
                    <HealthBadge state={u.alert_state} />
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <span className="text-xs text-muted-foreground">Freshness</span>
                      <p className="font-medium">
                        {u.freshness_hours !== null
                          ? `${u.freshness_hours.toFixed(1)}h`
                          : 'N/A'}
                      </p>
                    </div>
                    <div>
                      <span className="text-xs text-muted-foreground">Last Retrain</span>
                      <p className="font-medium">
                        {u.last_retrain_at
                          ? new Date(u.last_retrain_at).toLocaleDateString()
                          : 'Never'}
                      </p>
                    </div>
                    <div>
                      <span className="text-xs text-muted-foreground">Open Alerts</span>
                      <p className="font-medium">{u.open_alert_count}</p>
                    </div>
                    <div>
                      <span className="text-xs text-muted-foreground">Correlation</span>
                      <p className="font-medium">
                        {u.conviction_correlation !== null
                          ? u.conviction_correlation.toFixed(3)
                          : 'N/A'}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

function RunsTab(): JSX.Element {
  return (
    <Card>
      <CardContent className="py-12 text-center">
        <p className="text-muted-foreground">Training run history coming soon.</p>
      </CardContent>
    </Card>
  )
}
