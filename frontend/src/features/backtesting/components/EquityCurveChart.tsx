import { useEffect, useRef } from 'react'
import { createChart, ColorType, AreaSeries, type IChartApi } from 'lightweight-charts'

interface EquityCurveChartProps {
  readonly equityCurve: readonly { readonly date: string; readonly value: number }[]
}

export function EquityCurveChart({ equityCurve }: EquityCurveChartProps): JSX.Element {
  const containerRef = useRef<HTMLDivElement>(null)
  const chartRef = useRef<IChartApi | null>(null)

  useEffect(() => {
    if (!containerRef.current || equityCurve.length === 0) return

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 300,
      layout: {
        background: { type: ColorType.Solid, color: '#ffffff' },
        textColor: '#333',
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      timeScale: {
        timeVisible: false,
      },
    })

    const series = chart.addSeries(AreaSeries, {
      lineColor: '#2563eb',
      topColor: 'rgba(37, 99, 235, 0.3)',
      bottomColor: 'rgba(37, 99, 235, 0.02)',
      lineWidth: 2,
    })

    series.setData(
      equityCurve.map((d) => ({
        time: d.date,
        value: d.value,
      })),
    )

    chart.timeScale().fitContent()
    chartRef.current = chart

    const handleResize = () => {
      if (containerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: containerRef.current.clientWidth })
      }
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      if (chartRef.current) {
        chartRef.current.remove()
        chartRef.current = null
      }
    }
  }, [equityCurve])

  return <div ref={containerRef} className="w-full rounded-md border bg-white" />
}
