import { Card, CardContent } from '../../../shared/components/ui/card'
import { usePipelineRuns } from '../api/usePipelineRuns'
import { PipelineRunsTable } from '../components/PipelineRunsTable'

export function PipelineRunsPage(): JSX.Element {
  const { data, isLoading, isError, error } = usePipelineRuns()

  const runs = data?.runs ?? []
  const successRate = data?.success_rate

  return (
    <main className="mx-auto max-w-6xl p-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Pipeline Runs</h1>
        <p className="text-muted-foreground mt-1">
          Recent Prefect flow runs across all pipelines.
        </p>
      </div>

      <div className="space-y-6">
        {successRate != null && (
          <Card>
            <CardContent className="flex items-center gap-6 py-6">
              <div className="flex items-center gap-3">
                <div
                  className="flex h-16 w-16 items-center justify-center rounded-full text-lg font-bold text-white"
                  style={{
                    backgroundColor:
                      successRate >= 0.95
                        ? '#16a34a'
                        : successRate >= 0.85
                          ? '#d97706'
                          : '#dc2626',
                  }}
                >
                  {Math.round(successRate * 100)}%
                </div>
                <div>
                  <p className="text-lg font-semibold">Pipeline Success Rate</p>
                  <p className="text-muted-foreground text-sm">
                    Last {runs.length} runs
                  </p>
                </div>
              </div>
              <div className="ml-auto">
                <a
                  href="http://localhost:4200"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary text-sm font-medium hover:underline"
                >
                  Open Prefect UI &rarr;
                </a>
              </div>
            </CardContent>
          </Card>
        )}

        {isLoading && (
          <p className="text-muted-foreground text-sm">
            Loading pipeline runs...
          </p>
        )}

        {isError && (
          <div className="rounded-md bg-red-50 p-4">
            <p className="text-sm text-red-600" role="alert">
              {error instanceof Error
                ? error.message
                : 'Failed to load pipeline runs'}
            </p>
          </div>
        )}

        {!isLoading && !isError && <PipelineRunsTable runs={runs} />}
      </div>
    </main>
  )
}
