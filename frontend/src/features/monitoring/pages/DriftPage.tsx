import { useState } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { useModelHealth } from '../api/useModelHealth'
import { useDriftData } from '../api/useDriftData'
import { Card, CardContent } from '../../../shared/components/ui/card'

export function DriftPage(): JSX.Element {
  const { data: healthData, isLoading: healthLoading } = useModelHealth()
  const [universeId, setUniverseId] = useState('')

  const {
    data: driftData,
    isLoading: driftLoading,
    isError,
    error,
  } = useDriftData(universeId || '')

  const universes = healthData ?? []

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="flex flex-wrap items-end gap-4 py-4">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-muted-foreground">Universe</label>
            <select
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={universeId}
              onChange={(e) => setUniverseId(e.target.value)}
            >
              <option value="">Select universe...</option>
              {universes.map((u) => (
                <option key={u.universe_id} value={u.universe_id}>
                  {u.universe_name}
                </option>
              ))}
            </select>
          </div>
        </CardContent>
      </Card>

      {healthLoading && (
        <div className="h-16 animate-pulse rounded-lg bg-gray-100" />
      )}

      {!universeId && !healthLoading && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">Select a universe to view feature drift.</p>
          </CardContent>
        </Card>
      )}

      {universeId && driftLoading && (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-8 animate-pulse rounded bg-gray-100" />
          ))}
        </div>
      )}

      {universeId && isError && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-red-600" role="alert">
              {error instanceof Error ? error.message : 'Failed to load drift data'}
            </p>
          </CardContent>
        </Card>
      )}

      {universeId && driftData && !driftLoading && !isError && (
        <>
          {driftData.computed_at && (
            <p className="text-xs text-muted-foreground">
              Computed: {new Date(driftData.computed_at).toLocaleString()}
            </p>
          )}

          {driftData.features.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center">
                <p className="text-muted-foreground">No drift data available.</p>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="py-5">
                <h3 className="mb-4 text-sm font-semibold">
                  KL Divergence by Feature
                </h3>
                <ResponsiveContainer width="100%" height={Math.max(300, driftData.features.length * 24)}>
                  <BarChart
                    data={[...driftData.features].sort((a, b) => b.kl_divergence - a.kl_divergence)}
                    layout="vertical"
                    margin={{ left: 140, right: 20, top: 5, bottom: 5 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis type="number" tick={{ fontSize: 10 }} />
                    <YAxis
                      type="category"
                      dataKey="feature_name"
                      tick={{ fontSize: 10 }}
                      width={130}
                    />
                    <Tooltip
                      formatter={(value: number) => value.toFixed(4)}
                      labelFormatter={(label: string) => `Feature: ${label}`}
                    />
                    <Bar dataKey="kl_divergence" radius={[0, 4, 4, 0]}>
                      {[...driftData.features]
                        .sort((a, b) => b.kl_divergence - a.kl_divergence)
                        .map((f) => (
                          <Cell
                            key={f.feature_name}
                            fill={f.breached ? '#ef4444' : '#2563eb'}
                          />
                        ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {driftData.features.length > 0 && (
            <Card>
              <CardContent className="py-5">
                <h3 className="mb-3 text-sm font-semibold">Feature Details</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b text-xs font-medium text-muted-foreground">
                        <th className="p-2">Feature</th>
                        <th className="p-2">KL Divergence</th>
                        <th className="p-2">Threshold</th>
                        <th className="p-2">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...driftData.features]
                        .sort((a, b) => b.kl_divergence - a.kl_divergence)
                        .map((f) => (
                          <tr
                            key={f.feature_name}
                            className={`border-t ${f.breached ? 'bg-red-50' : ''}`}
                          >
                            <td className="p-2 font-mono text-xs">{f.feature_name}</td>
                            <td className="p-2 font-mono text-xs">
                              {f.kl_divergence.toFixed(4)}
                            </td>
                            <td className="p-2 font-mono text-xs">{f.threshold.toFixed(3)}</td>
                            <td className="p-2">
                              <span
                                className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                                  f.breached
                                    ? 'bg-red-100 text-red-800'
                                    : 'bg-green-100 text-green-800'
                                }`}
                              >
                                {f.breached ? 'Breached' : 'OK'}
                              </span>
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  )
}
