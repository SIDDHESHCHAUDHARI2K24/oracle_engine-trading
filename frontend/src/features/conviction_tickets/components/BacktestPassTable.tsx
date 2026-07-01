import { cn } from '../../../shared/utils/cn'

interface BacktestPassTableProps {
  readonly backtestPasses: number
  readonly passStrategies: readonly string[]
  readonly strategyLabels?: readonly string[]
}

const DEFAULT_LABELS = [
  'Mean Reversion',
  'Momentum Cross',
  'Volatility Breakout',
  'Statistical Arbitrage',
] as const

const KEY_MAP: Record<string, string> = {
  mean_reversion: 'Mean Reversion',
  momentum_cross: 'Momentum Cross',
  volatility_breakout: 'Volatility Breakout',
  stat_arb: 'Statistical Arbitrage',
}

export function BacktestPassTable({
  backtestPasses,
  passStrategies,
  strategyLabels = DEFAULT_LABELS,
}: BacktestPassTableProps): JSX.Element {
  const strategies = strategyLabels.map((label) => {
    const key = Object.entries(KEY_MAP).find(([, v]) => v === label)?.[0] ?? label
    const passed = passStrategies.includes(key) || passStrategies.includes(label)
    return { label, passed }
  })

  return (
    <div className="overflow-hidden rounded-md border">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b bg-gray-50 text-xs font-medium text-muted-foreground">
            <th className="p-2">Strategy</th>
            <th className="p-2 text-center">Result</th>
          </tr>
        </thead>
        <tbody>
          {strategies.map((s) => (
            <tr key={s.label} className="border-t last:border-b-0">
              <td className="p-2">{s.label}</td>
              <td className="p-2 text-center">
                <span
                  className={cn(
                    'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
                    s.passed
                      ? 'bg-green-100 text-green-800'
                      : 'bg-red-100 text-red-800',
                  )}
                >
                  {s.passed ? 'PASS' : 'FAIL'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="border-t bg-gray-50 px-2 py-1 text-xs text-muted-foreground">
        {backtestPasses} / {strategyLabels.length} strategies passed
      </div>
    </div>
  )
}
