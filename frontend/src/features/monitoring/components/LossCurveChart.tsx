import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'

interface LossCurveChartProps {
  readonly data: readonly {
    readonly epoch: number
    readonly train_loss: number
    readonly val_loss: number
  }[]
}

export function LossCurveChart({ data }: LossCurveChartProps): JSX.Element {
  if (data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-md border bg-white text-sm text-muted-foreground">
        No loss curve data available
      </div>
    )
  }

  return (
    <div className="rounded-md border bg-white p-4">
      <h3 className="mb-3 text-sm font-semibold">Training &amp; Validation Loss</h3>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
          <XAxis dataKey="epoch" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip />
          <Legend />
          <Line
            type="monotone"
            dataKey="train_loss"
            stroke="#2563eb"
            strokeWidth={2}
            dot={false}
            name="Train Loss"
          />
          <Line
            type="monotone"
            dataKey="val_loss"
            stroke="#f97316"
            strokeWidth={2}
            dot={false}
            name="Val Loss"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
