interface ConformalIntervalBarProps {
  readonly lower: number
  readonly predicted: number
  readonly upper: number
}

export function ConformalIntervalBar({
  lower,
  predicted,
  upper,
}: ConformalIntervalBarProps): JSX.Element {
  const span = upper - lower || 0.001
  const predictedPct = ((predicted - lower) / span) * 100

  return (
    <div className="w-full space-y-1">
      <div className="relative h-4 w-full rounded-full bg-gray-200">
        <div
          className="absolute top-0 h-full rounded-full bg-blue-200"
          style={{ left: `${Math.max(0, ((lower - lower) / span) * 100)}%`, width: '100%' }}
        />
        <div
          className="absolute top-0 h-4 w-2.5 -translate-x-1/2 rounded-full bg-blue-600"
          style={{ left: `${Math.min(100, Math.max(0, predictedPct))}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{lower.toFixed(2)}%</span>
        <span className="font-medium text-blue-700">{predicted.toFixed(2)}%</span>
        <span>{upper.toFixed(2)}%</span>
      </div>
    </div>
  )
}
