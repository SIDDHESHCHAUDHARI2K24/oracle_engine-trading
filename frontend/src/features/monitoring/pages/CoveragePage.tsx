import { useState } from 'react'
import { useModelHealth } from '../api/useModelHealth'
import { useCoverageData } from '../api/useCoverageData'
import { CoverageChart } from '../components/CoverageChart'
import { Card, CardContent } from '../../../shared/components/ui/card'

const HORIZONS = ['1d', '5d', '21d']

export function CoveragePage(): JSX.Element {
  const { data: healthData, isLoading: healthLoading } = useModelHealth()
  const [universeId, setUniverseId] = useState('')
  const [horizon, setHorizon] = useState('5d')

  const {
    data: coverageData,
    isLoading: coverageLoading,
    isError,
    error,
  } = useCoverageData(universeId || '', horizon)

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

          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-muted-foreground">Horizon</label>
            <select
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={horizon}
              onChange={(e) => setHorizon(e.target.value)}
            >
              {HORIZONS.map((h) => (
                <option key={h} value={h}>
                  {h}
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
            <p className="text-muted-foreground">Select a universe to view coverage data.</p>
          </CardContent>
        </Card>
      )}

      {universeId && coverageLoading && (
        <div className="h-64 animate-pulse rounded-lg bg-gray-100" />
      )}

      {universeId && isError && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-red-600" role="alert">
              {error instanceof Error ? error.message : 'Failed to load coverage data'}
            </p>
          </CardContent>
        </Card>
      )}

      {universeId && coverageData && !coverageLoading && !isError && (
        <CoverageChart data={coverageData} horizon={horizon} />
      )}
    </div>
  )
}
