import { useState, useMemo } from 'react'
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  useReactTable,
  type Row,
} from '@tanstack/react-table'
import { Button } from '../../../shared/components/ui/button'
import { Card, CardContent } from '../../../shared/components/ui/card'
import { useSystemAlerts } from '../api/useSystemAlerts'
import { useAcknowledgeAlert } from '../api/useAcknowledgeAlert'
import { useResolveAlert } from '../api/useResolveAlert'
import type { SystemAlert, AlertSeverity } from '../../../core/types'
import { clsx } from 'clsx'

export function AlertsPage(): JSX.Element {
  return (
    <main className="mx-auto max-w-6xl p-8">
      <div className="mb-6">
        <h1 className="text-3xl font-bold">System Alerts</h1>
        <p className="text-muted-foreground mt-1">
          View, acknowledge, and resolve monitoring alerts.
        </p>
      </div>
      <AlertsContent />
    </main>
  )
}

function AlertsContent(): JSX.Element {
  const [severityFilter, setSeverityFilter] = useState<AlertSeverity | ''>('')
  const [universeIdFilter, setUniverseIdFilter] = useState('')
  const [resolveConfirmId, setResolveConfirmId] = useState<string | null>(null)
  const [acknowledgingId, setAcknowledgingId] = useState<string | null>(null)

  const { data, isLoading, isError, error } = useSystemAlerts({
    severity: severityFilter || undefined,
    universe_id: universeIdFilter || undefined,
  })

  const uniqueUniverses = useMemo(() => {
    if (!data) return []
    const map = new Map<string, string>()
    for (const a of data.alerts) {
      if (a.universe_id && a.universe_name) {
        map.set(a.universe_id, a.universe_name)
      }
    }
    return [...map.entries()].map(([id, name]) => ({ id, name }))
  }, [data])

  const alerts = data?.alerts ?? []

  const columns = useMemo<ColumnDef<SystemAlert>[]>(
    () => [
      {
        accessorKey: 'severity',
        header: 'Severity',
        cell: ({ getValue }) => (
          <SeverityBadge severity={getValue<AlertSeverity>()} />
        ),
      },
      {
        accessorKey: 'code',
        header: 'Code',
        cell: ({ getValue }) => (
          <span className="font-mono text-xs">{getValue<string>()}</span>
        ),
      },
      {
        accessorKey: 'universe_name',
        header: 'Universe',
        cell: ({ getValue }) => {
          const val = getValue<string | null>()
          return val ? (
            <span className="text-sm">{val}</span>
          ) : (
            <span className="text-muted-foreground">&mdash;</span>
          )
        },
      },
      {
        accessorKey: 'message',
        header: 'Message',
        cell: ({ getValue }) => (
          <span className="max-w-[300px] truncate text-sm">{getValue<string>()}</span>
        ),
      },
      {
        accessorKey: 'created_at',
        header: 'Age',
        cell: ({ getValue }) => (
          <span className="text-sm tabular-nums">
            {formatAlertAge(getValue<string>())}
          </span>
        ),
      },
      {
        id: 'actions',
        header: '',
        cell: ({ row }: { readonly row: Row<SystemAlert> }) => (
          <AlertActions
            alert={row.original}
            isAcknowledging={acknowledgingId === row.original.id}
            isConfirmingResolve={resolveConfirmId === row.original.id}
            onAcknowledge={(id) => setAcknowledgingId(id)}
            onAcknowledgeDone={() => setAcknowledgingId(null)}
            onResolveClick={(id) => setResolveConfirmId(id)}
            onResolveDone={() => setResolveConfirmId(null)}
          />
        ),
      },
    ],
    [acknowledgingId, resolveConfirmId],
  )

  const table = useReactTable({
    data: alerts,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="flex flex-wrap items-end gap-4 py-4">
          <div>
            <label
              htmlFor="severity-filter"
              className="mb-1 block text-xs font-medium text-gray-500"
            >
              Severity
            </label>
            <select
              id="severity-filter"
              value={severityFilter}
              onChange={(e) =>
                setSeverityFilter(e.target.value as AlertSeverity | '')
              }
              className="rounded-md border px-3 py-2 text-sm"
            >
              <option value="">All severities</option>
              <option value="critical">Critical</option>
              <option value="warning">Warning</option>
              <option value="info">Info</option>
            </select>
          </div>
          <div>
            <label
              htmlFor="universe-filter"
              className="mb-1 block text-xs font-medium text-gray-500"
            >
              Universe
            </label>
            <select
              id="universe-filter"
              value={universeIdFilter}
              onChange={(e) => setUniverseIdFilter(e.target.value)}
              className="rounded-md border px-3 py-2 text-sm"
            >
              <option value="">All universes</option>
              {uniqueUniverses.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name}
                </option>
              ))}
            </select>
          </div>
        </CardContent>
      </Card>

      {isLoading && (
        <p className="text-muted-foreground text-sm">Loading alerts...</p>
      )}

      {isError && (
        <div className="rounded-md bg-red-50 p-4">
          <p className="text-sm text-red-600" role="alert">
            {error instanceof Error ? error.message : 'Failed to load alerts'}
          </p>
        </div>
      )}

      {!isLoading && !isError && (
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
                <tr
                  key={row.id}
                  className={clsx(
                    'hover:bg-gray-50',
                    row.original.severity === 'critical' &&
                      !row.original.resolved &&
                      'bg-red-50/30',
                  )}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-3 text-sm">
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {alerts.length === 0 && (
            <div className="px-4 py-8 text-center text-sm text-gray-500">
              No alerts found.
            </div>
          )}
        </div>
      )}

      {resolveConfirmId !== null && (
        <ResolveConfirmDialog
          onConfirm={() => setResolveConfirmId(null)}
          onCancel={() => setResolveConfirmId(null)}
        />
      )}
    </div>
  )
}

function SeverityBadge({
  severity,
}: {
  readonly severity: AlertSeverity
}): JSX.Element {
  const colors: Record<AlertSeverity, string> = {
    critical: 'bg-red-100 text-red-800 border-red-200',
    warning: 'bg-amber-100 text-amber-800 border-amber-200',
    info: 'bg-blue-100 text-blue-800 border-blue-200',
  }
  return (
    <span
      className={clsx(
        'inline-block rounded-full border px-2 py-0.5 text-xs font-medium',
        colors[severity],
      )}
    >
      {severity}
    </span>
  )
}

function AlertActions({
  alert,
  isAcknowledging,
  isConfirmingResolve,
  onAcknowledge,
  onAcknowledgeDone,
  onResolveClick,
  onResolveDone,
}: {
  readonly alert: SystemAlert
  readonly isAcknowledging: boolean
  readonly isConfirmingResolve: boolean
  readonly onAcknowledge: (id: string) => void
  readonly onAcknowledgeDone: () => void
  readonly onResolveClick: (id: string) => void
  readonly onResolveDone: () => void
}): JSX.Element {
  const acknowledgeMutation = useAcknowledgeAlert(alert.id)
  const resolveMutation = useResolveAlert(alert.id)

  const handleAcknowledge = () => {
    onAcknowledge(alert.id)
    acknowledgeMutation.mutate(undefined, {
      onSettled: () => onAcknowledgeDone(),
    })
  }

  const handleResolve = () => {
    resolveMutation.mutate(undefined, {
      onSettled: () => onResolveDone(),
    })
  }

  if (alert.resolved) {
    return (
      <span className="text-xs text-gray-400">Resolved</span>
    )
  }

  if (isConfirmingResolve) {
    return (
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500">Resolve this alert?</span>
        <Button
          type="button"
          size="sm"
          variant="destructive"
          onClick={handleResolve}
          disabled={resolveMutation.isPending}
        >
          Yes
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={() => onResolveDone()}
        >
          No
        </Button>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2">
      {!alert.acknowledged && (
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={handleAcknowledge}
          disabled={isAcknowledging && acknowledgeMutation.isPending}
        >
          {isAcknowledging && acknowledgeMutation.isPending
            ? '...'
            : 'Acknowledge'}
        </Button>
      )}
      <Button
        type="button"
        size="sm"
        variant="destructive"
        onClick={() => onResolveClick(alert.id)}
      >
        Resolve
      </Button>
    </div>
  )
}

function ResolveConfirmDialog({
  onConfirm,
  onCancel,
}: {
  readonly onConfirm: () => void
  readonly onCancel: () => void
}): JSX.Element {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-xl">
        <h3 className="text-lg font-semibold">Resolve Alert</h3>
        <p className="text-muted-foreground mt-2 text-sm">
          Are you sure you want to resolve this alert? This action cannot be
          undone.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="button" variant="destructive" onClick={onConfirm}>
            Resolve
          </Button>
        </div>
      </div>
    </div>
  )
}

function formatAlertAge(iso: string): string {
  const then = new Date(iso).getTime()
  const now = Date.now()
  const diff = now - then
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d`
  return new Date(iso).toLocaleDateString()
}
