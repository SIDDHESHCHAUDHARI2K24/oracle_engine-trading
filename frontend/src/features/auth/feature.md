# Auth Feature (Frontend)

The `auth` feature handles user authentication: the login form, JWT access
token storage in memory, silent refresh via HttpOnly cookie, and the
`ProtectedRoute` guard that gates all authenticated pages.

## Responsibilities

- Render the login page at `/login` with email + password form.
- Call `POST /auth/login`, receive the JWT access token and user object, and
  store them in the Zustand auth store (memory only — never localStorage).
- Redirect to `/universes` on successful login.
- Provide `ProtectedRoute` to redirect unauthenticated visitors to `/login`.
- Expose `apiClient` to all features; it reads the access token from the
  Zustand store and injects it as an `Authorization: Bearer` header.
- Handle `401` responses globally: clear auth state and redirect to `/login`.

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

### `pages/LoginPage.tsx`

React component rendered at `/login`:

- Uses `react-hook-form` + Zod schema (`loginSchema`) for validation.
- Zod rules: `email` must be a valid email address; `password` must be
  non-empty.
- Renders a shadcn `Card` centred on a full-height grey background.
- Field errors are shown inline with `role="alert"` and `aria-describedby`
  for accessibility.
- API-level errors (wrong credentials, server error) are shown as a single
  red paragraph above the submit button.
- Submit button is disabled and shows "Signing in…" while the mutation is
  pending.
- No redirect logic in the component — that lives in `useLogin.onSuccess`.

### `core/auth-context.tsx` (shared infrastructure, owned by core)

`ProtectedRoute` component:

```typescript
// Redirects to /login if accessToken is null
export function ProtectedRoute({ children }: { children: ReactNode }): JSX.Element
```

Reads `accessToken` from the Zustand store. Returns `<Navigate to="/login" replace />`
if absent, otherwise renders `{children}` inside a fragment.

## Route wiring (`App.tsx`)

```
/login       → LoginPage (unprotected)
/universes   → UniverseListPage wrapped in ProtectedRoute
/            → Navigate to /universes (triggers ProtectedRoute → /login if unauthenticated)
*            → Navigate to /universes
```

## Types (`core/types.ts`)

```typescript
type UserId = string & { readonly __brand: 'UserId' }

interface UserResponse {
  id: UserId
  email: string
  is_admin: boolean
  created_at: string
}

interface TokenResponse {
  access_token: string
  token_type: string
  user: UserResponse
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

## Backlog / Future Enhancements

- Implement silent token refresh: intercept `401`, call `POST /auth/refresh`,
  retry the original request, and only redirect to `/login` if refresh also
  fails.
- Add `useLogout` mutation hook that calls `POST /auth/logout` and clears the
  Zustand store.
- Add Account Settings page for password change.
- Add session list page (`GET /auth/sessions`) and "log out everywhere" action.
