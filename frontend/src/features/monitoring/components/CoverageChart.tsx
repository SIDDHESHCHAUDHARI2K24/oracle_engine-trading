import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Legend,
} from 'recharts'

interface CoverageChartProps {
  readonly data: readonly {
    readonly date: string
    readonly coverage: number
    readonly nominal: number
    readonly breach_threshold: number
  }[]
  readonly horizon: string
}

export function CoverageChart({ data, horizon }: CoverageChartProps): JSX.Element {
  if (data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-md border bg-white text-sm text-muted-foreground">
        No coverage data available
      </div>
    )
  }

  return (
    <div className="rounded-md border bg-white p-4">
      <h3 className="mb-3 text-sm font-semibold">{horizon} Coverage</h3>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 11 }}
            tickFormatter={(d: string) => d.slice(0, 7)}
          />
          <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
          <Tooltip
            formatter={(value) => [`${((value as number) * 100).toFixed(1)}%`]}
            labelFormatter={(label) => `Date: ${label as string}`}
          />
          <Legend />
          <Line
            type="monotone"
            dataKey="coverage"
            stroke="#2563eb"
            strokeWidth={2}
            dot={false}
            name="Realized"
          />
          <Line
            type="monotone"
            dataKey="nominal"
            stroke="#6b7280"
            strokeWidth={1.5}
            strokeDasharray="5 5"
            dot={false}
            name="Nominal (90%)"
          />
          <ReferenceLine
            y={0.8}
            stroke="#ef4444"
            strokeWidth={1}
            strokeDasharray="4 4"
            label={{ value: 'Breach (80%)', position: 'right', fontSize: 10, fill: '#ef4444' }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
