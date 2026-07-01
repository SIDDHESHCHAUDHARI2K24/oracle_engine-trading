import { useParams, Link } from 'react-router-dom'
import { useBacktestDetail } from '../api/useBacktestDetail'
import { EquityCurveChart } from '../components/EquityCurveChart'
import { DrawdownChart } from '../components/DrawdownChart'
import { Button } from '../../../shared/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../../../shared/components/ui/card'
import type { StrategyMetrics } from '../../../core/types'

function formatPct(value: number | null): string {
  if (value === null) return '\u2014'
  return `${(value * 100).toFixed(2)}%`
}

function formatNum(value: number | null, decimals = 2): string {
  if (value === null) return '\u2014'
  return value.toFixed(decimals)
}

export function TickerDetailPage(): JSX.Element {
  const { universeId, tickerId } = useParams<{ universeId: string; tickerId: string }>()
  const uid = universeId ?? ''
  const tid = tickerId ?? ''
  const { data, isLoading, isError, error } = useBacktestDetail(uid, tid)

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Loading backtest detail...</p>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <p className="text-red-600" role="alert">
            {error instanceof Error ? error.message : 'Failed to load backtest detail'}
          </p>
          <Link to={`/backtests/${uid}`}>
            <Button type="button" variant="outline" className="mt-4">
              Back to Explorer
            </Button>
          </Link>
        </div>
      </div>
    )
  }

  if (!data) return <></>

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-8">
      <div className="flex items-center gap-3">
        <Link to={`/backtests/${uid}`}>
          <Button type="button" variant="outline">
            Back to Explorer
          </Button>
        </Link>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="font-mono">{data.symbol}</CardTitle>
          <p className="text-sm text-muted-foreground">
            {data.strategies.length} strategies evaluated
          </p>
        </CardHeader>
      </Card>

      {data.strategies.map((strategy) => (
        <StrategySection key={strategy.strategy_name} strategy={strategy} />
      ))}
    </div>
  )
}

function StrategySection({
  strategy,
}: {
  readonly strategy: StrategyMetrics
}): JSX.Element {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-lg capitalize">
          {strategy.strategy_name.replace(/_/g, ' ')}
        </CardTitle>
        <span
          className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
            strategy.passed
              ? 'bg-green-100 text-green-800'
              : 'bg-red-100 text-red-800'
          }`}
        >
          {strategy.passed ? 'PASS' : 'FAIL'}
        </span>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="overflow-hidden rounded-md border">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b bg-gray-50 text-xs font-medium text-muted-foreground">
                <th className="p-2">Sharpe Ratio</th>
                <th className="p-2">Max Drawdown</th>
                <th className="p-2">Total Return</th>
                <th className="p-2">Win Rate</th>
                <th className="p-2">Profit Factor</th>
                <th className="p-2">Total Trades</th>
              </tr>
            </thead>
            <tbody>
              <tr className="text-center font-medium">
                <td className="p-2">{formatNum(strategy.sharpe_ratio)}</td>
                <td className="p-2">{formatPct(strategy.max_drawdown)}</td>
                <td className="p-2">{formatPct(strategy.total_return)}</td>
                <td className="p-2">{formatPct(strategy.win_rate)}</td>
                <td className="p-2">{formatNum(strategy.profit_factor)}</td>
                <td className="p-2">{strategy.total_trades ?? '\u2014'}</td>
              </tr>
            </tbody>
          </table>
        </div>

        {strategy.equity_curve && strategy.equity_curve.length > 0 && (
          <div>
            <h4 className="mb-2 text-sm font-medium text-muted-foreground">
              Equity Curve
            </h4>
            <EquityCurveChart equityCurve={strategy.equity_curve} />
          </div>
        )}

        {strategy.equity_curve && strategy.equity_curve.length > 0 && (
          <div>
            <h4 className="mb-2 text-sm font-medium text-muted-foreground">
              Drawdown
            </h4>
            <DrawdownChart equityCurve={strategy.equity_curve} />
          </div>
        )}

        {(!strategy.equity_curve || strategy.equity_curve.length === 0) && (
          <p className="text-sm text-muted-foreground py-4 text-center">
            No equity curve data available.
          </p>
        )}
      </CardContent>
    </Card>
  )
}
