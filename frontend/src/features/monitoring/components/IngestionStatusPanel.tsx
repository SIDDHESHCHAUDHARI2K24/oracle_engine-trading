import { Button } from '../../../shared/components/ui/button'
import { Card, CardContent } from '../../../shared/components/ui/card'
import { useIngestStatus } from '../api/useIngestStatus'
import { useTriggerIngestion } from '../api/useTriggerIngestion'

export function IngestionStatusPanel(): JSX.Element {
  const { data, isLoading, isError, error, refetch } = useIngestStatus()
  const triggerMutation = useTriggerIngestion()

  const handleRefresh = () => {
    refetch()
  }

  const handleTrigger = () => {
    triggerMutation.mutate({ mode: 'incremental' })
  }

  return (
    <Card>
      <CardContent className="py-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Data Ingestion Status</h2>
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={handleRefresh} disabled={isLoading}>
              Refresh
            </Button>
            <Button
              type="button"
              onClick={handleTrigger}
              disabled={triggerMutation.isPending}
            >
              {triggerMutation.isPending ? 'Triggering...' : 'Trigger Refresh'}
            </Button>
          </div>
        </div>

        {isLoading && (
          <p className="text-muted-foreground text-sm">Loading ingestion status...</p>
        )}

        {isError && (
          <div className="rounded-md bg-red-50 p-4">
            <p className="text-sm text-red-600" role="alert">
              {error instanceof Error ? error.message : 'Failed to load ingestion status'}
            </p>
          </div>
        )}

        {data && !isLoading && !isError && (
          <div className="space-y-4">
            {data.latest_run ? (
              <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                <StatusBadge
                  label="Status"
                  value={data.latest_run.status}
                  variant={
                    data.latest_run.status === 'succeeded'
                      ? 'success'
                      : data.latest_run.status === 'partial'
                        ? 'warning'
                        : data.latest_run.status === 'failed'
                          ? 'error'
                          : 'neutral'
                  }
                />
                <div>
                  <p className="text-muted-foreground text-xs">OHLCV Rows</p>
                  <p className="text-sm font-medium">
                    {data.latest_run.ohlcv_rows_inserted.toLocaleString()}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">Failed Tickers</p>
                  <p className="text-sm font-medium">
                    {data.latest_run.failed_tickers?.length ?? 0}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">Macro Stale</p>
                  <p className="text-sm font-medium">
                    {data.latest_run.stale_macro ? (
                      <span className="text-amber-600">Yes</span>
                    ) : (
                      <span className="text-green-600">No</span>
                    )}
                  </p>
                </div>
              </div>
            ) : (
              <p className="text-muted-foreground text-sm">
                No ingestion runs yet. Run the backfill to start.
              </p>
            )}

            {triggerMutation.isError && (
              <div className="rounded-md bg-red-50 p-3">
                <p className="text-sm text-red-600" role="alert">
                  {triggerMutation.error instanceof Error
                    ? triggerMutation.error.message
                    : 'Trigger failed'}
                </p>
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function StatusBadge({
  label,
  value,
  variant,
}: {
  readonly label: string
  readonly value: string
  readonly variant: 'success' | 'warning' | 'error' | 'neutral'
}): JSX.Element {
  const colors: Record<string, string> = {
    success: 'bg-green-100 text-green-800',
    warning: 'bg-amber-100 text-amber-800',
    error: 'bg-red-100 text-red-800',
    neutral: 'bg-gray-100 text-gray-800',
  }

  return (
    <div>
      <p className="text-muted-foreground text-xs">{label}</p>
      <span
        className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${colors[variant]}`}
      >
        {value}
      </span>
    </div>
  )
}
