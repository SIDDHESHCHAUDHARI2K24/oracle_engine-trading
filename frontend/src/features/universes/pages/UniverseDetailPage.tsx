import { useState, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { useUniverse } from '../api/useUniverse'
import { useMembership } from '../api/useMembership'
import { useAddMembers } from '../api/useAddMembers'
import { useRemoveMember } from '../api/useRemoveMember'
import { useImportCsv } from '../api/useImportCsv'
import { Button } from '../../../shared/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '../../../shared/components/ui/card'
import type { AddResult, ImportResult, TickerSummary } from '../../../core/types'

function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '\u2014'
  return new Date(dateStr).toLocaleDateString()
}

function StatusBadge({ isSystem }: { readonly isSystem: boolean }): JSX.Element {
  if (isSystem) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
        <svg
          className="h-3 w-3"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
          />
        </svg>
        System Managed
      </span>
    )
  }
  return (
    <span className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-700">
      Custom
    </span>
  )
}

function AddResultPanel({ result, onClose }: { readonly result: AddResult | ImportResult; readonly onClose: () => void }): JSX.Element {
  const parseErrors = 'parse_errors' in result ? result.parse_errors : []
  return (
    <div className="rounded-md border bg-gray-50 p-4 mt-3 space-y-2">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold">Result</h4>
        <button
          type="button"
          className="text-muted-foreground hover:text-foreground text-sm"
          onClick={onClose}
        >
          Dismiss
        </button>
      </div>
      <ul className="text-sm space-y-1">
        <li className="text-green-700">{result.added.length} added</li>
        <li className="text-amber-700">{result.already_present.length} already present</li>
        {result.invalid.length > 0 && (
          <li className="text-red-700">
            {result.invalid.length} invalid: {result.invalid.join(', ')}
          </li>
        )}
      </ul>
      {parseErrors.length > 0 && (
        <div className="text-sm text-red-600">
          <p className="font-medium">Parse Errors:</p>
          <ul className="list-disc pl-5">
            {parseErrors.map((err, i) => (
              <li key={i}>{err}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function ConfirmDialog({
  message,
  onConfirm,
  onCancel,
}: {
  readonly message: string
  readonly onConfirm: () => void
  readonly onCancel: () => void
}): JSX.Element {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-sm rounded-lg bg-white p-6 shadow-lg">
        <p className="text-sm mb-4">{message}</p>
        <div className="flex justify-end gap-3">
          <Button type="button" variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            type="button"
            className="bg-red-600 hover:bg-red-700 focus-visible:ring-red-600"
            onClick={onConfirm}
          >
            Remove
          </Button>
        </div>
      </div>
    </div>
  )
}

function AddTickersSection({
  universeId,
  onAddResult,
}: {
  readonly universeId: string
  readonly onAddResult: (r: AddResult) => void
}): JSX.Element {
  const [input, setInput] = useState('')
  const addMembers = useAddMembers(universeId)

  const handleAdd = (): void => {
    const symbols = input
      .split(/[,\n]+/)
      .map((s) => s.trim().toUpperCase())
      .filter((s) => s.length > 0)
    if (symbols.length === 0) return
    addMembers.mutate(symbols, {
      onSuccess: (result) => {
        onAddResult(result)
        setInput('')
      },
    })
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Add Tickers</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <textarea
          rows={4}
          className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2"
          placeholder="Paste symbols, separated by commas or newlines..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
        />
        <Button
          type="button"
          disabled={addMembers.isPending || input.trim().length === 0}
          onClick={handleAdd}
        >
          {addMembers.isPending ? 'Adding...' : 'Add'}
        </Button>
      </CardContent>
    </Card>
  )
}

function CsvImportSection({
  universeId,
  onImportResult,
}: {
  readonly universeId: string
  readonly onImportResult: (r: ImportResult) => void
}): JSX.Element {
  const importCsv = useImportCsv(universeId)

  const onDrop = useCallback(
    (acceptedFiles: readonly File[]) => {
      const file = acceptedFiles[0]
      if (!file) return
      importCsv.mutate(file, {
        onSuccess: (result) => {
          onImportResult(result)
        },
      })
    },
    [importCsv, onImportResult],
  )

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'] },
    maxFiles: 1,
    disabled: importCsv.isPending,
  })

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Import CSV</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <div
          {...getRootProps()}
          className={`flex cursor-pointer flex-col items-center justify-center rounded-md border-2 border-dashed p-8 text-center text-sm transition-colors ${
            isDragActive
              ? 'border-blue-500 bg-blue-50'
              : 'border-gray-300 hover:border-gray-400'
          } ${importCsv.isPending ? 'pointer-events-none opacity-50' : ''}`}
        >
          <input {...getInputProps()} />
          {importCsv.isPending ? (
            <p className="text-muted-foreground">Uploading...</p>
          ) : isDragActive ? (
            <p className="text-blue-600">Drop CSV file here</p>
          ) : (
            <p className="text-muted-foreground">
              Drag & drop a CSV file here, or click to select
            </p>
          )}
        </div>
      </CardContent>
    </Card>
  )
}

function MembershipTable({
  universeId,
  tickers,
  atDate,
}: {
  readonly universeId: string
  readonly tickers: readonly TickerSummary[]
  readonly atDate?: string
}): JSX.Element {
  const [removeConfirm, setRemoveConfirm] = useState<string | null>(null)
  const removeMember = useRemoveMember(universeId)

  const handleRemove = (): void => {
    if (!removeConfirm) return
    removeMember.mutate(removeConfirm, {
      onSuccess: () => setRemoveConfirm(null),
    })
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-lg">
          Membership
          {atDate && (
            <span className="ml-2 text-sm font-normal text-muted-foreground">
              as of {atDate}
            </span>
          )}
        </CardTitle>
        <span className="text-sm text-muted-foreground">{tickers.length} tickers</span>
      </CardHeader>
      <CardContent className="p-0">
        {removeConfirm && (
          <ConfirmDialog
            message="Remove this ticker from the universe?"
            onConfirm={handleRemove}
            onCancel={() => setRemoveConfirm(null)}
          />
        )}
        <table className="w-full text-left">
          <thead>
            <tr className="border-b text-sm font-medium text-muted-foreground">
              <th className="p-3">Symbol</th>
              <th className="p-3">Name</th>
              <th className="p-3">Exchange</th>
              <th className="p-3">Asset Type</th>
              <th className="p-3">Added</th>
              <th className="p-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {tickers.length === 0 && (
              <tr>
                <td colSpan={6} className="p-6 text-center text-sm text-muted-foreground">
                  No tickers in this universe
                </td>
              </tr>
            )}
            {tickers.map((ticker) => (
              <tr key={ticker.id} className="border-t hover:bg-gray-50">
                <td className="p-3 text-sm font-mono font-medium">{ticker.symbol}</td>
                <td className="p-3 text-sm">{ticker.name}</td>
                <td className="p-3 text-sm text-muted-foreground">{ticker.exchange ?? '\u2014'}</td>
                <td className="p-3 text-sm">{ticker.asset_type}</td>
                <td className="p-3 text-sm text-muted-foreground">{formatDate(ticker.added_at)}</td>
                <td className="p-3">
                  <Button
                    type="button"
                    variant="ghost"
                    className="h-8 px-2 text-xs text-red-600 hover:bg-red-50"
                    disabled={removeMember.isPending}
                    onClick={() => setRemoveConfirm(ticker.id)}
                  >
                    Remove
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </CardContent>
    </Card>
  )
}

function DatePickerSection({
  value,
  onChange,
}: {
  readonly value: string
  readonly onChange: (d: string) => void
}): JSX.Element {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 py-3">
        <label htmlFor="at-date" className="text-sm font-medium">
          View as of:
        </label>
        <input
          id="at-date"
          type="date"
          className="rounded-md border border-input bg-background px-3 py-1.5 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2"
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        {value && (
          <span className="text-sm text-muted-foreground">
            Showing membership as of {value}
          </span>
        )}
      </CardContent>
    </Card>
  )
}

export function UniverseDetailPage(): JSX.Element {
  const { id } = useParams<{ id: string }>()
  const universeId = id ?? ''
  const { data: universe, isLoading, isError, error } = useUniverse(universeId)
  const [addResult, setAddResult] = useState<AddResult | null>(null)
  const [importResult, setImportResult] = useState<ImportResult | null>(null)
  const [atDate, setAtDate] = useState('')

  const {
    data: tickers,
    isLoading: isLoadingTickers,
    isError: isErrorTickers,
    error: errorTickers,
  } = useMembership(universeId, atDate || undefined)

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Loading universe...</p>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-red-600" role="alert">
          {error instanceof Error ? error.message : 'Failed to load universe'}
        </p>
      </div>
    )
  }

  if (!universe) return <></>

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-8">
      <div className="flex items-center gap-3">
        <Link to="/universes">
          <Button type="button" variant="outline">
            Back to Universes
          </Button>
        </Link>
        {!universe.is_system_managed && (
          <Link to={`/universes/${universe.id}/edit`}>
            <Button type="button">Edit</Button>
          </Link>
        )}
      </div>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between">
          <div className="space-y-1">
            <CardTitle>{universe.display_name}</CardTitle>
            <p className="text-sm font-mono text-muted-foreground">{universe.name}</p>
          </div>
          <div className="flex items-center gap-2">
            <StatusBadge isSystem={universe.is_system_managed} />
            {universe.public_id && (
              <span className="inline-flex items-center rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-medium text-purple-800 font-mono">
                {universe.public_id}
              </span>
            )}
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-muted-foreground">Created</dt>
              <dd>{formatDate(universe.created_at)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Tickers</dt>
              <dd>{universe.ticker_count}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Last Retrain</dt>
              <dd>
                {universe.last_retrain_at ? (
                  formatDate(universe.last_retrain_at)
                ) : (
                  <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                    Never
                  </span>
                )}
              </dd>
            </div>
          </dl>
          {universe.description && (
            <div>
              <dt className="text-sm text-muted-foreground">Description</dt>
              <dd className="text-sm mt-1">{universe.description}</dd>
            </div>
          )}
        </CardContent>
      </Card>

      <AddTickersSection universeId={universeId} onAddResult={setAddResult} />
      {addResult && (
        <AddResultPanel result={addResult} onClose={() => setAddResult(null)} />
      )}

      <CsvImportSection universeId={universeId} onImportResult={setImportResult} />
      {importResult && (
        <AddResultPanel result={importResult} onClose={() => setImportResult(null)} />
      )}

      <DatePickerSection value={atDate} onChange={setAtDate} />

      {isLoadingTickers && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">Loading membership...</p>
          </CardContent>
        </Card>
      )}

      {isErrorTickers && (
        <Card>
          <CardContent className="py-6 text-center">
            <p className="text-red-600" role="alert">
              {errorTickers instanceof Error
                ? errorTickers.message
                : 'Failed to load membership'}
            </p>
          </CardContent>
        </Card>
      )}

      {!isLoadingTickers && !isErrorTickers && tickers && (
        <MembershipTable universeId={universeId} tickers={tickers} atDate={atDate || undefined} />
      )}

      <Card>
        <CardContent className="py-6 text-center">
          <p className="text-sm text-muted-foreground">
            Model Health &mdash; Coming in S4
          </p>
        </CardContent>
      </Card>
    </div>
  )
}
