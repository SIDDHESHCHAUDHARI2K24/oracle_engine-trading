import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useUniverses } from '../api/useUniverses'
import { Button } from '../../../shared/components/ui/button'
import { Card, CardContent } from '../../../shared/components/ui/card'
import type { UniverseSummary } from '../../../core/types'

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '\u2014'
  return new Date(dateStr).toLocaleDateString()
}

function StatusBadge({ isSystem }: { readonly isSystem: boolean }): JSX.Element {
  if (isSystem) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
        <LockIcon />
        System
      </span>
    )
  }
  return (
    <span className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-700">
      Custom
    </span>
  )
}

function LockIcon(): JSX.Element {
  return (
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
  )
}

function UniverseRow({ universe }: { readonly universe: UniverseSummary }): JSX.Element {
  return (
    <tr className="border-t hover:bg-gray-50">
      <td className="p-3 text-sm font-medium">
        <Link
          to={`/universes/${universe.id}`}
          className="text-blue-600 hover:text-blue-800 hover:underline"
        >
          {universe.display_name}
        </Link>
      </td>
      <td className="p-3 text-sm text-muted-foreground font-mono">{universe.name}</td>
      <td className="p-3 text-sm">{universe.ticker_count}</td>
      <td className="p-3">
        <StatusBadge isSystem={universe.is_system_managed} />
      </td>
      <td className="p-3 text-sm text-muted-foreground">
        {universe.last_retrain_at ? (
          formatDate(universe.last_retrain_at)
        ) : (
          <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
            Never
          </span>
        )}
      </td>
      <td className="p-3 text-sm">
        {!universe.is_system_managed && (
          <Link
            to={`/universes/${universe.id}/edit`}
            className="text-blue-600 hover:text-blue-800 hover:underline"
          >
            Edit
          </Link>
        )}
      </td>
    </tr>
  )
}

export function UniverseListPage(): JSX.Element {
  const [includeDeleted, setIncludeDeleted] = useState(false)
  const { data, isLoading, isError, error, refetch } = useUniverses(includeDeleted)

  return (
    <main className="mx-auto max-w-6xl p-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-3xl font-bold">Universes</h1>
        <div className="flex items-center gap-3">
          <Button type="button" variant="outline" onClick={() => refetch()}>
            Refresh
          </Button>
          <Link to="/universes/new">
            <Button type="button">New Universe</Button>
          </Link>
        </div>
      </div>

      <Card className="mb-6">
        <CardContent className="py-4">
          <label className="flex items-center gap-2 text-sm cursor-pointer">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-600"
              checked={includeDeleted}
              onChange={(e) => setIncludeDeleted(e.target.checked)}
            />
            Include deleted
          </label>
        </CardContent>
      </Card>

      {isLoading && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">Loading universes...</p>
          </CardContent>
        </Card>
      )}

      {isError && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-red-600" role="alert">
              {error instanceof Error ? error.message : 'Failed to load universes'}
            </p>
            <Button type="button" variant="outline" className="mt-4" onClick={() => refetch()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {data && !isLoading && !isError && data.universes.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              No universes found. Create your first universe!
            </p>
          </CardContent>
        </Card>
      )}

      {data && data.universes.length > 0 && (
        <Card>
          <CardContent className="p-0">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b text-sm font-medium text-muted-foreground">
                  <th className="p-3">Name</th>
                  <th className="p-3">Slug</th>
                  <th className="p-3">Tickers</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Last Retrain</th>
                  <th className="p-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {data.universes.map((universe) => (
                  <UniverseRow key={universe.id} universe={universe} />
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
      )}
    </main>
  )
}
