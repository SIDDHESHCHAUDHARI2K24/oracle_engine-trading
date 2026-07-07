import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from '@tanstack/react-table'
import { Button } from '../../../shared/components/ui/button'
import type { PipelineRunInfo } from '../../../core/types'
import { clsx } from 'clsx'

const columns: ColumnDef<PipelineRunInfo>[] = [
  {
    accessorKey: 'name',
    header: 'Flow Name',
    cell: ({ getValue }) => {
      const name = getValue<string>()
      return (
        <span className="max-w-[220px] truncate font-medium" title={name}>
          {name}
        </span>
      )
    },
  },
  {
    accessorKey: 'status',
    header: 'Status',
    cell: ({ getValue }) => {
      const status = getValue<string>()
      return <StatusBadge status={status} />
    },
  },
  {
    accessorKey: 'started_at',
    header: 'Started',
    cell: ({ getValue }) => {
      const val = getValue<string | null>()
      if (!val) return <span className="text-muted-foreground">&mdash;</span>
      return <span className="text-sm">{formatRelative(val)}</span>
    },
    sortingFn: 'datetime',
  },
  {
    accessorKey: 'duration_seconds',
    header: 'Duration',
    cell: ({ getValue }) => {
      const val = getValue<number | null>()
      if (val == null) return <span className="text-muted-foreground">&mdash;</span>
      return <span className="text-sm tabular-nums">{formatDuration(val)}</span>
    },
  },
  {
    accessorKey: 'success',
    header: 'Result',
    cell: ({ getValue }) => {
      const val = getValue<boolean | null>()
      if (val == null)
        return <span className="text-muted-foreground text-sm">Running</span>
      return (
        <span
          className={clsx(
            'inline-block rounded-full px-2 py-0.5 text-xs font-medium',
            val
              ? 'bg-green-100 text-green-800'
              : 'bg-red-100 text-red-800',
          )}
        >
          {val ? 'Success' : 'Failed'}
        </span>
      )
    },
  },
  {
    id: 'actions',
    header: '',
    cell: ({ row }) => {
      const url = row.original.prefect_ui_url
      if (!url) return null
      return (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-primary text-xs font-medium hover:underline"
        >
          View in Prefect &rarr;
        </a>
      )
    },
  },
]

interface PipelineRunsTableProps {
  readonly runs: readonly PipelineRunInfo[]
}

export function PipelineRunsTable({ runs }: PipelineRunsTableProps): JSX.Element {
  const table = useReactTable({
    data: runs,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th
                  key={header.id}
                  className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wider text-gray-500"
                >
                  {flexRender(
                    header.column.columnDef.header,
                    header.getContext(),
                  )}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody className="divide-y divide-gray-200 bg-white">
          {table.getRowModel().rows.map((row) => (
            <tr key={row.id} className="hover:bg-gray-50">
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="px-4 py-3 text-sm">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {runs.length === 0 && (
        <div className="px-4 py-8 text-center text-sm text-gray-500">
          No pipeline runs found.
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status }: { readonly status: string }): JSX.Element {
  const isRunning = status === 'RUNNING' || status === 'PENDING' || status === 'SCHEDULED'

  const colors: Record<string, string> = {
    COMPLETED: 'bg-green-100 text-green-800',
    FAILED: 'bg-red-100 text-red-800',
    CANCELLED: 'bg-gray-100 text-gray-800',
    RUNNING: 'bg-blue-100 text-blue-800',
    PENDING: 'bg-yellow-100 text-yellow-800',
    SCHEDULED: 'bg-purple-100 text-purple-800',
    CRASHED: 'bg-red-100 text-red-800',
    PAUSED: 'bg-amber-100 text-amber-800',
  }

  return (
    <span className="inline-flex items-center gap-1.5">
      {isRunning && (
        <svg
          className="h-3 w-3 animate-spin text-blue-600"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
      )}
      <span
        className={clsx(
          'inline-block rounded-full px-2 py-0.5 text-xs font-medium',
          colors[status] ?? 'bg-gray-100 text-gray-800',
        )}
      >
        {status}
      </span>
    </span>
  )
}

function formatRelative(iso: string): string {
  const then = new Date(iso).getTime()
  const now = Date.now()
  const diff = now - then
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return `${seconds}s ago`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(iso).toLocaleDateString()
}

function formatDuration(secs: number): string {
  if (secs < 60) return `${secs.toFixed(0)}s`
  const minutes = Math.floor(secs / 60)
  const remaining = Math.round(secs % 60)
  if (minutes < 60) return `${minutes}m ${remaining}s`
  const hours = Math.floor(minutes / 60)
  const remMin = minutes % 60
  return `${hours}h ${remMin}m`
}
