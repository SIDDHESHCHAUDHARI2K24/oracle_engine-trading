import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ZAxis,
  ReferenceLine,
} from 'recharts'

interface CorrelationChartProps {
  readonly data: readonly {
    readonly universe_id: string
    readonly universe_name: string
    readonly conviction_correlation: number | null
  }[]
}

export function CorrelationChart({ data }: CorrelationChartProps): JSX.Element {
  const chartData = data
    .filter((d) => d.conviction_correlation !== null)
    .map((d) => ({
      name: d.universe_name,
      x: d.universe_name.length,
      y: d.conviction_correlation as number,
    }))

  if (chartData.length === 0) {
    return (
      <div className="flex h-48 items-center justify-center rounded-md border bg-white text-sm text-muted-foreground">
        No conviction correlation data
      </div>
    )
  }

  return (
    <div className="rounded-md border bg-white p-4">
      <h3 className="mb-3 text-sm font-semibold">Conviction Correlation by Universe</h3>
      <ResponsiveContainer width="100%" height={180}>
        <ScatterChart>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="name" tick={{ fontSize: 10 }} />
          <YAxis domain={[-1, 1]} tick={{ fontSize: 10 }} />
          <ZAxis range={[60, 60]} />
          <Tooltip
            formatter={(value: number) => value.toFixed(3)}
            labelFormatter={(label: string) => label}
          />
          <ReferenceLine y={0} stroke="#6b7280" strokeWidth={1} />
          <Scatter
            data={chartData}
            fill="#2563eb"
            name="Correlation"
          />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  )
}
