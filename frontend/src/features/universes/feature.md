# Universes Feature (Frontend)

The `universes` feature renders the main authenticated view of the
application: a list of all equity universes available to the ML pipeline.

## Responsibilities

- Fetch and display all universes from `GET /api/v1/universes`.
- Handle loading, error, and empty states explicitly.
- Serve as the default landing page after login (`/universes`).

## Files

### `pages/UniverseListPage.tsx`

React component rendered at `/universes` (protected route):

- Calls `useUniverses()` to fetch the universe list.
- **Loading state**: renders a loading indicator while the query is in flight.
- **Error state**: renders an error message if the query fails.
- **Empty state**: renders a meaningful message when `total === 0`.
- **Success state**: renders each universe's `display_name` and `name`.
- The component is the only consumer of `useUniverses`; no prop drilling.

### `api/useUniverses.ts` (planned — not yet created)

TanStack Query `useQuery` hook:

```typescript
// Query key: ['universes', 'list']
// Query fn: apiClient.get<UniverseListResponse>('/api/v1/universes')
export function useUniverses(): UseQueryResult<UniverseListResponse, Error>
```

Refetch policy: on-demand only (manual refresh button). No polling interval
for the universe list — it changes infrequently.

## Types (`core/types.ts`)

```typescript
type UniverseId = string & { readonly __brand: 'UniverseId' }

interface UniverseSummary {
  id: UniverseId
  name: string           // machine-readable slug, e.g. "sp500"
  display_name: string   // human-readable label, e.g. "S&P 500"
  is_system_managed: boolean
  created_at: string
}

interface UniverseListResponse {
  universes: readonly UniverseSummary[]
  total: number
}
```

## Route wiring

`/universes` is wrapped in `ProtectedRoute` in `App.tsx`. Unauthenticated
visitors are redirected to `/login` before the page renders.

## Current state

`UniverseListPage` is implemented and functional for the walking-skeleton
milestone (S0). The `useUniverses` hook has not yet been extracted into its
own file — query logic currently lives inline in the page component.

Pending S1 work:
- Extract `useUniverses` to `api/useUniverses.ts` with proper query key factory.
- Add `UniverseDetailPage` at `/universes/:id` using `useUniverseDetail`.
- Add `useUniverseDetail`, `useAddMembers`, `useRemoveMember`, `useImportCsv`
  hooks once backend write endpoints are available.
- Add a manual refresh button (invalidate query key on click).
- Virtualize the ticker list in `UniverseDetailPage` if membership count
  exceeds 100 visible rows (TanStack Virtual).

## Backlog / Future Enhancements

- Universe detail page with paginated, searchable ticker table.
- Point-in-time membership snapshot via `?at=<date>` query parameter.
- Bulk ticker add (form) and CSV import for non-system-managed universes.
- Universe create / delete for non-system-managed universes.
- System-managed universe badge — prevent rename/delete in UI for universes
  where `is_system_managed === true`.
