import { useParams, Link, useNavigate } from 'react-router-dom'
import { useBacktestSummary } from '../api/useBacktestSummary'
import { Button } from '../../../shared/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../../../shared/components/ui/card'
import type { TickerPassEntry } from '../../../core/types'

const STRATEGY_LABELS = [
  'mean_reversion',
  'momentum_cross',
  'volatility_breakout',
  'stat_arb',
] as const

export function ExplorerPage(): JSX.Element {
  const { universeId } = useParams<{ universeId: string }>()
  const uid = universeId ?? ''
  const navigate = useNavigate()
  const { data, isLoading, isError, error } = useBacktestSummary(uid)

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Loading backtest results...</p>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <p className="text-red-600" role="alert">
            {error instanceof Error ? error.message : 'Failed to load backtest results'}
          </p>
          <Link to="/universes">
            <Button type="button" variant="outline" className="mt-4">
              Back to Universes
            </Button>
          </Link>
        </div>
      </div>
    )
  }

  if (!data) return <></>

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-8">
      <div className="flex items-center gap-3">
        <Link to="/universes">
          <Button type="button" variant="outline">
            Back to Universes
          </Button>
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Backtest Explorer</CardTitle>
          <p className="text-muted-foreground text-sm">
            Universe: {data.universe_id}
            {data.run && (
              <span className="ml-3">
                Run {data.run.status} | {data.run.backtest_period_start} &mdash;{' '}
                {data.run.backtest_period_end}
              </span>
            )}
          </p>
        </CardHeader>
        <CardContent>
          {data.tickers.length === 0 && (
            <p className="text-muted-foreground text-sm py-6 text-center">
              No backtest results available for this universe.
            </p>
          )}

          {data.tickers.length > 0 && (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
              {data.tickers.map((ticker) => (
                <TickerPassCard
                  key={ticker.ticker_id}
                  ticker={ticker}
                  onClick={() =>
                    navigate(`/backtests/${uid}/${ticker.ticker_id}`)
                  }
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

function TickerPassCard({
  ticker,
  onClick,
}: {
  readonly ticker: TickerPassEntry
  readonly onClick: () => void
}): JSX.Element {
  return (
    <button
      type="button"
      className="rounded-md border p-3 text-left hover:bg-gray-50 transition-colors cursor-pointer"
      onClick={onClick}
    >
      <p className="text-sm font-mono font-medium text-blue-600">{ticker.symbol}</p>
      <p className="mt-1 text-xs text-muted-foreground">
        {ticker.passes} / {STRATEGY_LABELS.length} passed
      </p>
      <div className="mt-2 flex gap-1.5">
        {STRATEGY_LABELS.map((key) => (
          <span
            key={key}
            className={`h-2.5 w-2.5 rounded-full ${
              ticker.strategies[key] ? 'bg-green-500' : 'bg-red-400'
            }`}
            title={`${key.replace(/_/g, ' ')}: ${ticker.strategies[key] ? 'PASS' : 'FAIL'}`}
          />
        ))}
      </div>
    </button>
  )
}
