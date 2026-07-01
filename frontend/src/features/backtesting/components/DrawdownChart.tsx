import { useMemo } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceArea,
} from 'recharts'

interface DrawdownChartProps {
  readonly equityCurve: readonly { readonly date: string; readonly value: number }[]
}

interface DrawdownPoint {
  date: string
  drawdown: number
}

export function DrawdownChart({ equityCurve }: DrawdownChartProps): JSX.Element {
  const data: readonly DrawdownPoint[] = useMemo(() => {
    if (equityCurve.length === 0) return []
    let peak = equityCurve[0]?.value ?? 0
    return equityCurve.map((d) => {
      if (d.value > peak) peak = d.value
      const drawdown = peak !== 0 ? ((d.value - peak) / peak) * 100 : 0
      return { date: d.date, drawdown: Math.round(drawdown * 100) / 100 }
    })
  }, [equityCurve])

  if (data.length === 0) {
    return (
      <div className="flex h-[200px] items-center justify-center text-sm text-muted-foreground">
        No data available
      </div>
    )
  }

  const maxDrawdown = Math.min(...data.map((d) => d.drawdown))

  return (
    <ResponsiveContainer width="100%" height={200}>
      <LineChart data={data as DrawdownPoint[]} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
        <ReferenceArea
          y1={0}
          y2={Infinity}
          fill="rgba(239, 68, 68, 0.05)"
          stroke="none"
        />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          interval="preserveStartEnd"
        />
        <YAxis
          tick={{ fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={(v: number) => `${v}%`}
          domain={[Math.floor(maxDrawdown * 1.1), 5]}
        />
        <Tooltip
          formatter={(value) => [`${value}%`, 'Drawdown']}
          labelStyle={{ fontSize: 12 }}
          contentStyle={{ fontSize: 12 }}
        />
        <Line
          type="monotone"
          dataKey="drawdown"
          stroke="#ef4444"
          dot={false}
          strokeWidth={1.5}
          fill="rgba(239, 68, 68, 0.1)"
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
