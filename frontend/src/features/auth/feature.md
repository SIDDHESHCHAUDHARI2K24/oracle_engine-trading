# Auth Feature (Frontend)

The `auth` feature handles user authentication: login form, JWT access token
storage in memory, silent refresh via HttpOnly cookie, `ProtectedRoute` guard,
account settings page, and session management.

## Responsibilities

- Render the login page at `/login` with email + password form.
- Call `POST /auth/login`, receive the JWT access token and user object, and
  store them in the Zustand auth store (memory only — never localStorage).
- Redirect to `/universes` on successful login.
- Provide `ProtectedRoute` to redirect unauthenticated visitors to `/login`.
- Expose `apiClient` to all features; it reads the access token from the
  Zustand store and injects it as an `Authorization: Bearer` header.
- Handle `401` responses globally: clear auth state and redirect to `/login`.
- Provide `AccountSettingsPage` at `/settings/account` with change-password
  form, session list, and logout-everywhere action.

## Pages

### `LoginPage` (`/login`)

- `react-hook-form` + Zod schema (`loginSchema`): valid email + non-empty password.
- shadcn `Card` centred on a full-height grey background.
- Field errors shown inline with `role="alert"` and `aria-describedby`.
- API-level errors shown as a single red paragraph above the submit button.
- Submit button disabled with "Signing in…" while mutation is pending.
- Calls `useLogin` mutation hook; navigation lives in `onSuccess`, not the component.

### `AccountSettingsPage` (`/settings/account`)

- **Change password form**: RHF + Zod, `new_password` min 12 chars. Calls
  `POST /api/v1/auth/change-password`. Shows success/error toast.
- **Sessions table**: polls `GET /api/v1/auth/sessions` every 60s via
  TanStack Query `refetchInterval: 60_000`. Columns: created_at, expires_at,
  user_agent, ip, "this device" badge (when `is_current === true`).
- **Log out everywhere**: button with shadcn `AlertDialog` confirm. Calls
  `POST /api/v1/auth/logout-everywhere`, clears auth store, redirects to `/login`.

## Files

### `store.ts`

Zustand store with two state fields and two actions:

```typescript
interface AuthState {
  accessToken: string | null   // JWT access token — NEVER written to localStorage
  user: UserResponse | null
  setAuth(token: string, user: UserResponse): void
  logout(): void
}
```

`setAuth` is called on successful login or token refresh.
`logout` clears both fields; `apiClient` redirects to `/login` automatically
when a `401` is received.

### `api/useLogin.ts`

TanStack Query `useMutation` hook:

- `mutationFn`: `POST /auth/login` with `{email, password}` via `apiClient.post`.
- `onSuccess`: calls `setAuth(data.access_token, data.user)` then navigates
  to `/universes` via React Router `useNavigate`.
- The hook is the single call site for login; `LoginPage` never touches
  `apiClient` directly.

### `api/useSessions.ts`

TanStack Query `useQuery` hook:

- Query key: `['auth', 'sessions']`
- Query fn: `apiClient.get('/api/v1/auth/sessions')`
- `refetchInterval: 60_000` for near-real-time polling.
- Returns `list[SessionInfo]`.

### `api/useLogoutEverywhere.ts`

TanStack Query `useMutation`:

- `mutationFn`: `POST /api/v1/auth/logout-everywhere`
- `onSuccess`: clears auth store, redirects to `/login`.

### `core/auth-context.tsx` (shared infrastructure, owned by core)

`ProtectedRoute` component:

```typescript
export function ProtectedRoute({ children }: { children: ReactNode }): JSX.Element
```

Reads `accessToken` from the Zustand store. Returns `<Navigate to="/login" replace />`
if absent, otherwise renders `{children}` inside a fragment.

## Route wiring (`App.tsx`)

```
/login            → LoginPage (unprotected)
/universes        → UniverseListPage wrapped in ProtectedRoute
/settings/account → AccountSettingsPage wrapped in ProtectedRoute
/                 → Navigate to /universes
*                 → Navigate to /universes
```

## Types (`core/types.ts`)

```typescript
type UserId = string & { readonly __brand: 'UserId' }

interface UserResponse {
  id: UserId
  email: string
  full_name: string | null
  is_admin: boolean
  created_at: string
}

interface TokenResponse {
  access_token: string
  token_type: string
  user: UserResponse
}

interface SessionInfo {
  id: string
  created_at: string
  expires_at: string
  last_used_at: string | null
  user_agent: string | null
  ip: string | null
  is_current: boolean
}
```

## Security notes

- `accessToken` lives only in the Zustand memory store. A hard refresh clears
  it; the user must log in again (silent refresh via cookie is planned).
- The refresh token is stored server-side in the `sessions` table and sent to
  the browser as an `HttpOnly Secure SameSite=Strict` cookie. The frontend
  never reads it directly.
- `POST /auth/refresh` (not yet wired in the frontend) will exchange the
  cookie for a new access token without requiring re-login.
- `credentials: 'include'` is set on every `fetch` call in `apiClient` so
  the refresh cookie is sent automatically.
- Password change requires 12-character minimum, enforced by both Zod and backend.

## Backlog / Future Enhancements

- Implement silent token refresh: intercept `401`, call `POST /auth/refresh`,
  retry the original request, and only redirect to `/login` if refresh also
  fails.
- Add `useLogout` mutation hook for single-session logout (currently backend-only).
