# Universes Feature (Frontend)

The `universes` feature renders the main authenticated view of the
application: a list of all equity universes, plus detail pages with
membership management and point-in-time history.

## Responsibilities

- Fetch and display all universes from `GET /api/v1/universes`.
- Handle loading, error, and empty states explicitly.
- Serve as the default landing page after login (`/universes`).
- Provide create/edit forms for non-system-managed universes.
- Show universe detail with ticker membership, CSV import, and point-in-time snapshots.

## Pages

### `UniverseListPage` (`/universes`)

- Calls `useUniverses()` with `?include_deleted` toggle (admin only).
- **Badges**: system-managed universes show a "System" badge; deleted universes
  show a "Deleted" badge.
- **Refresh button**: manually invalidates the query key.
- Each row links to `/universes/{id}`.

### `UniverseCreatePage` (`/universes/new`)

- RHF + Zod form: name (slug), display_name (label), description (optional).
- Calls `POST /api/v1/universes` via `useCreateUniverse` mutation.
- Redirects to new universe's detail page on success.
- Admin-only; non-admin users redirected with 403 toast.

### `UniverseEditPage` (`/universes/{id}/edit`)

- Pre-filled RHF form from `useUniverseDetail(id)`.
- Calls `PATCH /api/v1/universes/{id}` via `useUpdateUniverse` mutation.
- System-managed universes: form fields are read-only, toolbar shows
  "System-managed — read-only" notice.

### `UniverseDetailPage` (`/universes/{id}`)

Six sections:

1. **Header**: display_name, description, public_id, system-managed badge, edit/delete buttons.
2. **Active Members table**: paginated/sortable ticker list with remove action
   (confirm dialog via shadcn `AlertDialog`). Columns: symbol, name, exchange.
3. **Add Tickers**: textarea for symbol paste (newline/comma separated) +
   `useAddMembers` mutation. Returns breakdown: added / already present / invalid.
4. **CSV Import**: `react-dropzone` drag-drop zone. Calls
   `POST /{id}/membership/import` via `useImportCsv` mutation. Returns
   breakdown including parse_errors.
5. **Point-in-time View**: `react-day-picker` date picker. Calls
   `GET /{id}/membership?at=<date>` via `useMembersAtDate(id, date)`. Shows
   historical membership snapshot.
6. **Soft-delete**: delete button for non-system-managed universes (confirm dialog).
   Restore button visible when `?include_deleted=true` is active.

## Files

### `api/useUniverses.ts`

TanStack Query `useQuery` hook:

```typescript
// Query key: ['universes', 'list', includeDeleted]
// Query fn: apiClient.get('/api/v1/universes', { params: { include_deleted } })
export function useUniverses(includeDeleted?: boolean): UseQueryResult
```

### `api/useUniverseDetail.ts`

```typescript
// Query key: ['universes', 'detail', id]
// Query fn: apiClient.get(`/api/v1/universes/${id}`)
export function useUniverseDetail(id: string): UseQueryResult<UniverseDetail>
```

### `api/useCreateUniverse.ts`

```typescript
// mutationFn: apiClient.post('/api/v1/universes', body)
// onSuccess: navigate to detail page, invalidate list query
export function useCreateUniverse(): UseMutationResult
```

### `api/useUpdateUniverse.ts`

```typescript
// mutationFn: apiClient.patch(`/api/v1/universes/${id}`, body)
// onSuccess: invalidate detail + list queries
export function useUpdateUniverse(id: string): UseMutationResult
```

### `api/useDeleteUniverse.ts`

```typescript
// mutationFn: apiClient.delete(`/api/v1/universes/${id}`)
// onSuccess: invalidate list, navigate to /universes
export function useDeleteUniverse(id: string): UseMutationResult
```

### `api/useAddMembers.ts`

```typescript
// mutationFn: apiClient.post(`/api/v1/universes/${id}/membership`, { symbols })
// onSuccess: invalidate detail query
// Returns: AddResult { added, already_present, invalid }
export function useAddMembers(id: string): UseMutationResult<AddResult>
```

### `api/useImportCsv.ts`

```typescript
// mutationFn: multipart form upload via apiClient
// Returns: ImportResult extends AddResult { parse_errors: string[] }
export function useImportCsv(id: string): UseMutationResult<ImportResult>
```

### `api/useMembersAtDate.ts`

```typescript
// Query key: ['universes', 'members', id, dateIsoString]
// Query fn: apiClient.get(`/api/v1/universes/${id}/membership`, { params: { at: date } })
// Returns: list[TickerSummary]
export function useMembersAtDate(id: string, date: string | null): UseQueryResult
```

## Route wiring

```
/universes          → UniverseListPage (ProtectedRoute)
/universes/new      → UniverseCreatePage (ProtectedRoute, admin)
/universes/{id}     → UniverseDetailPage (ProtectedRoute)
/universes/{id}/edit → UniverseEditPage (ProtectedRoute, admin)
```

## Dependencies

- `react-dropzone` — drag-and-drop file upload for CSV import
- `react-day-picker` — date picker for point-in-time membership view
- `@tanstack/react-table` — paginated/sortable ticker table
- shadcn/ui: `Card`, `Table`, `Badge`, `Button`, `Dialog`, `AlertDialog`, `Textarea`, `Input`, `Form`, `Tabs`

## Types (`core/types.ts`)

```typescript
type UniverseId = string & { readonly __brand: 'UniverseId' }

interface UniverseSummary {
  id: UniverseId
  name: string
  display_name: string
  description: string | null
  public_id: string | null
  last_retrain_at: string | null
  is_system_managed: boolean
  created_at: string
  ticker_count: number
}

interface UniverseDetail extends UniverseSummary {
  tickers: TickerSummary[]
}

interface TickerSummary {
  id: string
  symbol: string
  name: string
  exchange: string | null
  asset_type: string
  active: boolean
}

interface AddResult {
  added: string[]
  already_present: string[]
  invalid: string[]
}
```

## Backlog / Future Enhancements

- Virtualize ticker list in `UniverseDetailPage` for universes with > 100 members
  (TanStack Virtual).
- Paginated ticker list at the API level for large universes (Russell 1000 = 1000 tickers).
