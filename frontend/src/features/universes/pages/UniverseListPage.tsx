import { useUniverses } from '../api/useUniverses'

export function UniverseListPage(): JSX.Element {
  const { data, isLoading, isError, error } = useUniverses()

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-muted-foreground">Loading universes\u2026</p>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-red-600" role="alert">
          {error instanceof Error ? error.message : 'Failed to load universes'}
        </p>
      </div>
    )
  }

  return (
    <main className="mx-auto max-w-4xl p-8">
      <h1 className="mb-6 text-3xl font-bold">Universes</h1>
      {data?.universes.length === 0 ? (
        <p className="text-muted-foreground">No universes found.</p>
      ) : (
        <ul className="space-y-3">
          {data?.universes.map((universe) => (
            <li
              key={universe.id}
              className="rounded-lg border bg-card p-4 text-card-foreground shadow-sm"
            >
              <h2 className="text-xl font-semibold">{universe.display_name}</h2>
              <p className="text-sm text-muted-foreground">{universe.name}</p>
              <p className="mt-1 text-sm text-muted-foreground">
                {universe.ticker_count} {universe.ticker_count === 1 ? 'ticker' : 'tickers'}
              </p>
            </li>
          ))}
        </ul>
      )}
    </main>
  )
}
