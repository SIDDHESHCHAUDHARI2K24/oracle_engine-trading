import { useParams, useNavigate } from 'react-router-dom'
import { useModelCard } from '../api/useModelCard'
import { Card, CardContent } from '../../../shared/components/ui/card'
import { Button } from '../../../shared/components/ui/button'
import { LossCurveChart } from '../components/LossCurveChart'

const coverageColor = (val: number): string => {
  if (val >= 0.85) return 'text-green-600'
  if (val >= 0.8) return 'text-amber-600'
  return 'text-red-600'
}

export function ModelCardPage(): JSX.Element {
  const { universeId } = useParams<{ readonly universeId: string }>()
  const navigate = useNavigate()
  const { data, isLoading, isError, error, refetch } = useModelCard(universeId ?? '')

  return (
    <main className="mx-auto max-w-6xl p-8">
      <div className="mb-6 flex items-center gap-4">
        <Button type="button" variant="ghost" onClick={() => navigate('/monitoring')}>
          &larr; Back
        </Button>
        <div>
          <h1 className="text-3xl font-bold">Model Card</h1>
          <p className="text-muted-foreground mt-1">
            {isLoading ? 'Loading...' : data?.universe_name ?? universeId}
          </p>
        </div>
      </div>

      {isLoading && (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-24 animate-pulse rounded-lg bg-gray-100" />
          ))}
        </div>
      )}

      {isError && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-red-600" role="alert">
              {error instanceof Error ? error.message : 'Failed to load model card'}
            </p>
            <Button type="button" variant="outline" className="mt-4" onClick={() => refetch()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {data && !isLoading && !isError && (
        <div className="space-y-6">
          <Card>
            <CardContent className="space-y-2 py-5">
              <h2 className="font-semibold">Last Training Run</h2>
              {data.last_training_run ? (
                <div className="grid grid-cols-2 gap-4 text-sm md:grid-cols-3">
                  <div>
                    <span className="text-xs text-muted-foreground">Run ID</span>
                    <p className="font-mono text-xs">{data.last_training_run.run_id}</p>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground">Trained At</span>
                    <p className="font-medium">
                      {new Date(data.last_training_run.trained_at).toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <span className="text-xs text-muted-foreground">Horizons</span>
                    <p className="font-medium">
                      {data.last_training_run.horizons.join(', ')}
                    </p>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">No training runs recorded.</p>
              )}
            </CardContent>
          </Card>

          {data.loss_curve && (
            <LossCurveChart data={data.loss_curve} />
          )}

          <Card>
            <CardContent className="space-y-3 py-5">
              <h2 className="font-semibold">Active Artifacts</h2>
              {data.artifacts.length === 0 ? (
                <p className="text-sm text-muted-foreground">No artifacts available.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b text-xs font-medium text-muted-foreground">
                        <th className="p-2">Artifact</th>
                        <th className="p-2">Horizon</th>
                        <th className="p-2">Trained</th>
                        <th className="p-2">MAE</th>
                        <th className="p-2">MSE</th>
                        <th className="p-2">Pearson</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.artifacts.map((a) => (
                        <tr key={a.artifact_key} className="border-t">
                          <td className="p-2 font-mono text-xs">{a.artifact_key}</td>
                          <td className="p-2">{a.horizon}</td>
                          <td className="p-2 text-xs">
                            {new Date(a.trained_at).toLocaleDateString()}
                          </td>
                          <td className="p-2 font-mono text-xs">
                            {a.val_mae?.toFixed(4) ?? '-'}
                          </td>
                          <td className="p-2 font-mono text-xs">
                            {a.val_mse?.toFixed(4) ?? '-'}
                          </td>
                          <td className="p-2 font-mono text-xs">
                            {a.val_pearson?.toFixed(4) ?? '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardContent className="space-y-3 py-5">
              <h2 className="font-semibold">Coverage</h2>
              {data.coverage.length === 0 ? (
                <p className="text-sm text-muted-foreground">No coverage data.</p>
              ) : (
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                  {data.coverage.map((c) => (
                    <div key={c.horizon} className="rounded-md border p-3">
                      <span className="text-xs text-muted-foreground">{c.horizon}</span>
                      <div className="mt-1 flex gap-3 text-sm">
                        <span>
                          <span className="text-xs text-muted-foreground">30d </span>
                          <span className={`font-semibold ${coverageColor(c.coverage_30d)}`}>
                            {(c.coverage_30d * 100).toFixed(1)}%
                          </span>
                        </span>
                        <span>
                          <span className="text-xs text-muted-foreground">90d </span>
                          <span className={`font-semibold ${coverageColor(c.coverage_90d)}`}>
                            {(c.coverage_90d * 100).toFixed(1)}%
                          </span>
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardContent className="space-y-3 py-5">
              <h2 className="font-semibold">Recent Tickets</h2>
              {data.recent_tickets.length === 0 ? (
                <p className="text-sm text-muted-foreground">No recent tickets.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b text-xs font-medium text-muted-foreground">
                        <th className="p-2">Ticker</th>
                        <th className="p-2">Horizon</th>
                        <th className="p-2">Conviction</th>
                        <th className="p-2">Return</th>
                        <th className="p-2">Direction</th>
                        <th className="p-2">Passes</th>
                        <th className="p-2">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent_tickets.map((t) => (
                        <tr
                          key={t.id}
                          className="cursor-pointer border-t hover:bg-gray-50"
                          onClick={() => navigate(`/tickets/${t.id}`)}
                        >
                          <td className="p-2 font-mono text-xs font-medium text-blue-600">
                            {t.ticker_id}
                          </td>
                          <td className="p-2">{t.horizon}</td>
                          <td className="p-2 font-mono text-xs">{t.conviction_score}</td>
                          <td className={`p-2 font-mono text-xs ${t.predicted_return > 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {t.predicted_return > 0 ? '+' : ''}{t.predicted_return.toFixed(2)}%
                          </td>
                          <td className="p-2">
                            <span
                              className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                                t.direction === 'LONG'
                                  ? 'bg-green-100 text-green-800'
                                  : 'bg-red-100 text-red-800'
                              }`}
                            >
                              {t.direction}
                            </span>
                          </td>
                          <td className="p-2 font-mono text-xs">{t.backtest_passes}/4</td>
                          <td className="p-2">
                            <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-800">
                              {t.status}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </main>
  )
}
