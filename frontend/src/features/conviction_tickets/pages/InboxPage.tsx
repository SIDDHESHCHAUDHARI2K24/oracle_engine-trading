import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  type SortingState,
  createColumnHelper,
  flexRender,
} from '@tanstack/react-table'
import { useTickets } from '../api/useTickets'
import { ConvictionBadge } from '../components/ConvictionBadge'
import { Button } from '../../../shared/components/ui/button'
import { Card, CardContent } from '../../../shared/components/ui/card'
import type { ConvictionTicket } from '../../../core/types'

const columnHelper = createColumnHelper<ConvictionTicket>()

const HORIZONS = ['', '1d', '5d', '21d']
const UNIVERSES = [
  { id: '', label: 'All Universes' },
  { id: 'sp500', label: 'S&P 500' },
  { id: 'nasdaq100', label: 'NASDAQ 100' },
  { id: 'russell2000', label: 'Russell 2000' },
]

export function InboxPage(): JSX.Element {
  const navigate = useNavigate()
  const [universeId, setUniverseId] = useState('')
  const [horizon, setHorizon] = useState('')
  const [minConviction, setMinConviction] = useState(0)
  const [minPasses, setMinPasses] = useState(0)
  const [sorting, setSorting] = useState<SortingState>([{ id: 'conviction_score', desc: true }])

  const { data, isLoading, isError, error, refetch } = useTickets(
    universeId || undefined,
    horizon || undefined,
    minConviction,
    minPasses,
  )

  const columns = useMemo(
    () => [
      columnHelper.accessor('id', {
        header: 'Ticker',
        cell: (info) => {
          const ticket = info.row.original
          return (
            <button
              type="button"
              className="font-mono text-sm font-medium text-blue-600 hover:text-blue-800 hover:underline"
              onClick={() => navigate(`/tickets/${ticket.id}`)}
            >
              {ticket.ticker_id}
            </button>
          )
        },
      }),
      columnHelper.accessor('universe_id', {
        header: 'Universe',
        cell: (info) => (
          <span className="text-sm text-muted-foreground">{info.getValue()}</span>
        ),
      }),
      columnHelper.accessor('horizon', {
        header: 'Horizon',
        cell: (info) => (
          <span className="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium">
            {info.getValue()}
          </span>
        ),
      }),
      columnHelper.accessor('conviction_score', {
        header: 'Conviction',
        cell: (info) => <ConvictionBadge score={info.getValue()} size="sm" />,
      }),
      columnHelper.accessor('predicted_return', {
        header: 'Return %',
        cell: (info) => {
          const val = info.getValue()
          return (
            <span className={`text-sm font-medium ${val > 0 ? 'text-green-600' : 'text-red-600'}`}>
              {val > 0 ? '+' : ''}
              {val.toFixed(2)}%
            </span>
          )
        },
      }),
      columnHelper.accessor('direction', {
        header: 'Direction',
        cell: (info) => {
          const dir = info.getValue()
          return (
            <span
              className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                dir === 'LONG'
                  ? 'bg-green-100 text-green-800'
                  : 'bg-red-100 text-red-800'
              }`}
            >
              {dir}
            </span>
          )
        },
      }),
      columnHelper.accessor('backtest_passes', {
        header: 'Backtest',
        cell: (info) => {
          const passes = info.getValue()
          return (
            <span className="text-sm font-medium">
              {passes}/4
            </span>
          )
        },
      }),
      columnHelper.accessor('status', {
        header: 'Status',
        cell: (info) => statusBadge(info.getValue()),
      }),
    ],
    [navigate],
  )

  const table = useReactTable({
    data: [...(data?.tickets ?? [])],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <main className="mx-auto max-w-6xl p-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">Conviction Tickets</h1>
        <p className="text-muted-foreground mt-1">
          Review AI-generated trading conviction tickets with backtest validation.
        </p>
      </div>

      <Card className="mb-6">
        <CardContent className="flex flex-wrap items-end gap-4 py-4">
          <FilterGroup label="Universe">
            <select
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={universeId}
              onChange={(e) => setUniverseId(e.target.value)}
            >
              {UNIVERSES.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.label}
                </option>
              ))}
            </select>
          </FilterGroup>

          <FilterGroup label="Horizon">
            <select
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={horizon}
              onChange={(e) => setHorizon(e.target.value)}
            >
              <option value="">All Horizons</option>
              {HORIZONS.filter((h) => h).map((h) => (
                <option key={h} value={h}>
                  {h}
                </option>
              ))}
            </select>
          </FilterGroup>

          <FilterGroup label={`Min Conviction: ${minConviction}`}>
            <input
              type="range"
              min={0}
              max={100}
              step={5}
              value={minConviction}
              onChange={(e) => setMinConviction(Number(e.target.value))}
              className="h-2 w-28 cursor-pointer"
            />
          </FilterGroup>

          <FilterGroup label="Min Passes">
            <select
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={minPasses}
              onChange={(e) => setMinPasses(Number(e.target.value))}
            >
              <option value={0}>Any</option>
              <option value={1}>1+</option>
              <option value={2}>2+</option>
              <option value={3}>3+</option>
              <option value={4}>4</option>
            </select>
          </FilterGroup>

          <Button type="button" variant="outline" onClick={() => refetch()}>
            Refresh
          </Button>
        </CardContent>
      </Card>

      {isLoading && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">Loading tickets...</p>
          </CardContent>
        </Card>
      )}

      {isError && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-red-600" role="alert">
              {error instanceof Error ? error.message : 'Failed to load tickets'}
            </p>
            <Button type="button" variant="outline" className="mt-4" onClick={() => refetch()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {data && !isLoading && !isError && data.tickets.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">No tickets found matching your filters.</p>
          </CardContent>
        </Card>
      )}

      {data && data.tickets.length > 0 && (
        <>
          <p className="mb-3 text-sm text-muted-foreground">
            Showing {data.tickets.length} of {data.total} tickets
          </p>
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    {table.getHeaderGroups().map((headerGroup) => (
                      <tr key={headerGroup.id} className="border-b text-xs font-medium text-muted-foreground">
                        {headerGroup.headers.map((header) => (
                          <th
                            key={header.id}
                            className={`p-3 ${header.column.getCanSort() ? 'cursor-pointer select-none hover:text-foreground' : ''}`}
                            onClick={header.column.getToggleSortingHandler()}
                          >
                            <div className="flex items-center gap-1">
                              {flexRender(header.column.columnDef.header, header.getContext())}
                              {{
                                asc: ' \u2191',
                                desc: ' \u2193',
                              }[header.column.getIsSorted() as string] ?? null}
                            </div>
                          </th>
                        ))}
                      </tr>
                    ))}
                  </thead>
                  <tbody>
                    {table.getRowModel().rows.map((row) => (
                      <tr
                        key={row.id}
                        className="border-t hover:bg-gray-50 cursor-pointer"
                        onClick={() => navigate(`/tickets/${row.original.id}`)}
                      >
                        {row.getVisibleCells().map((cell) => (
                          <td key={cell.id} className="p-3">
                            {flexRender(cell.column.columnDef.cell, cell.getContext())}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </main>
  )
}

function FilterGroup({ label, children }: { readonly label: string; readonly children: React.ReactNode }): JSX.Element {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-xs font-medium text-muted-foreground">{label}</label>
      {children}
    </div>
  )
}

function statusBadge(status: string): JSX.Element {
  const colors: Record<string, string> = {
    TRADABLE: 'bg-blue-100 text-blue-800',
    REVIEWED: 'bg-purple-100 text-purple-800',
    ACTIONED: 'bg-amber-100 text-amber-800',
    RESOLVED: 'bg-green-100 text-green-800',
    EXPIRED: 'bg-gray-100 text-gray-800',
  }
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${colors[status] ?? 'bg-gray-100 text-gray-800'}`}
    >
      {status}
    </span>
  )
}
