# Frontend — Agent Instructions (TypeScript + React)

> **Scope**: Frontend for MBI Labs Oracle Engine — Pipeline A
> **Companion docs**: `mbi-pipeline-a-v1-design.md`, `tech-stack-analysis.md`
> **For backend instructions**: See `agent-instructions/Pipeline-A-Agent-Instructions.md`

---

## 1. Frontend Tech Stack

| Layer | Technology | Version |
|---|---|---|
| Bundler | Vite | 5.x |
| Framework | React | 18.x |
| Language | TypeScript | 5.5+ (**strict mode**) |
| Routing | React Router | v6 |
| Server state | TanStack Query | v5 |
| Tables | TanStack Table | v8 (headless) |
| Forms | React Hook Form + Zod | RHF 7.x, Zod 3.x |
| Styling | Tailwind CSS + shadcn/ui | TW 3.4+, shadcn copied in |
| Financial charts | TradingView Lightweight Charts | 4.x (~45 KB, MIT) |
| General charts | Recharts | 2.x |
| Client state | Zustand | 4.x (minimal — auth + transient UI only) |
| Unit/component tests | vitest + @testing-library/react | latest |
| E2E tests | Playwright | latest |
| Linting | ESLint 9.x flat config | — |
| Formatting | Prettier | — |
| Package manager | pnpm | latest |
| Type generation | openapi-typescript | latest |

---

## 2. TypeScript Strict Mode Rules

**`tsconfig.json` must have:**
```json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noImplicitOverride": true,
    "noPropertyAccessFromIndexSignature": true
  }
}
```

### Mandatory Rules

1. **No `any`** — use `unknown` + type guards. If you must escape, use `// eslint-disable-next-line @typescript-eslint/no-explicit-any` with a comment explaining why.
2. **No non-null assertions (`!`)** — use optional chaining (`?.`) + defaults (`?? "fallback"`).
3. **Explicit return types** on all exported functions and React components.
4. **Branded types for IDs** — avoid mixing `string` with UUIDs:
```typescript
type UniverseId = string & { readonly __brand: "UniverseId" };
type TickerId = string & { readonly __brand: "TickerId" };
```
5. **Discriminated unions for API responses**:
```typescript
type ApiResponse<T> =
  | { status: "success"; data: T }
  | { status: "error"; error: ApiError };
```
6. **`readonly` arrays and objects** where data shouldn't mutate:
```typescript
const FEATURES: readonly string[] = ["auth", "universes"] as const;
```
7. **Enum-like patterns with `as const`** — prefer string literal unions over runtime enums:
```typescript
type TicketStatus = "TRADABLE" | "REVIEWED" | "ACTIONED" | "RESOLVED" | "EXPIRED";
```
8. **No `@ts-ignore`** — use `@ts-expect-error` with a comment if truly needed.

---

## 3. Clean Code Practices

Reference: `/typescript-clean-code` skill — load and consult before writing TypeScript.

### Rules

1. **Small functions** — < 20 lines. If longer, extract helpers.
2. **Meaningful names** — no abbreviations. `fetchActiveUniverses` not `getUnivs`.
3. **No magic numbers** — extract to named constants:
```typescript
const CONVICTION_THRESHOLD = 67;
const MIN_BACKTEST_PASSES = 2;
```
4. **DRY** — extract shared logic to hooks or utility functions. If you copy-paste, refactor.
5. **Single Responsibility** — one component does one thing. One hook fetches one query.
6. **Immutable data** — use `readonly`, `as const`, `Object.freeze()`. No direct state mutation.
7. **No commented-out code** — delete it. Git remembers.
8. **No console.log in production** — use a proper logger or remove.
9. **Meaningful error messages** — "Failed to fetch universes: network error" not "Error".
10. **Consistent naming**:
    - Components: PascalCase (`UniverseListPage.tsx`)
    - Hooks: camelCase with `use` prefix (`useUniverses.ts`)
    - Utils: camelCase (`formatCurrency.ts`)
    - Types: PascalCase (`UniverseResponse`, `TicketStatus`)
    - Constants: UPPER_SNAKE_CASE (`CONVICTION_THRESHOLD`)

---

## 4. React Component Conventions

### Directory Structure

```
frontend/src/
├── core/
│   ├── api-client.ts        # Central fetch wrapper
│   ├── query-client.ts      # TanStack Query client config
│   ├── auth-context.tsx     # Auth provider + route guard
│   └── types/
│       └── api.ts           # Auto-generated from OpenAPI
├── features/
│   ├── auth/
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   └── AccountSettingsPage.tsx
│   │   ├── api/
│   │   │   ├── useLogin.ts          # TanStack mutation
│   │   │   ├── useSessions.ts       # TanStack query
│   │   │   └── useChangePassword.ts # TanStack mutation
│   │   ├── components/
│   │   ├── store.ts                 # Zustand auth slice
│   │   └── LoginPage.test.tsx       # Colocated test
│   ├── universes/
│   │   ├── pages/
│   │   │   ├── UniverseListPage.tsx
│   │   │   ├── UniverseDetailPage.tsx
│   │   │   └── UniverseFormPage.tsx
│   │   ├── api/
│   │   │   ├── useUniverses.ts
│   │   │   ├── useUniverseDetail.ts
│   │   │   ├── useCreateUniverse.ts
│   │   │   ├── useUpdateUniverse.ts
│   │   │   ├── useMembership.ts
│   │   │   ├── useAddMembers.ts
│   │   │   ├── useRemoveMember.ts
│   │   │   └── useImportCsv.ts
│   │   └── components/
│   ├── tickets/
│   ├── monitoring/
│   └── ...
└── shared/
    ├── components/   # shadcn/ui primitives (Button, Dialog, Table, etc.)
    ├── hooks/        # Shared custom hooks
    └── utils/        # Shared utilities
```

### Component Rules

1. **One component per file**, named export. Default export only for lazy-loaded pages.
2. **Colocation**: tests, API hooks, and components live together in the feature directory.
3. **Custom hooks for all data fetching** — never call fetch/axios directly in components.
4. **React Hook Form** for all forms + Zod schema validation. Never hand-roll form state.
5. **Error boundaries** at feature level — one per feature route.
6. **Loading/error/success states** handled explicitly in every data-fetching component.
7. **No prop drilling > 2 levels** — use context or pull the data into a TanStack Query.
8. **Prefer composition over conditional rendering** — extract variants into separate components rather than complex ternaries.

---

## 5. TanStack Query Patterns

### Query Key Convention

```typescript
// Hierarchical, typed query keys
const universeKeys = {
  all: ["universes"] as const,
  lists: () => [...universeKeys.all, "list"] as const,
  list: (filters: UniverseFilters) => [...universeKeys.lists(), filters] as const,
  details: () => [...universeKeys.all, "detail"] as const,
  detail: (id: UniverseId) => [...universeKeys.details(), id] as const,
  membership: (id: UniverseId, at?: string) => [...universeKeys.detail(id), "membership", { at }] as const,
};
```

### Refetch Intervals (from design §11)

| Surface | Interval | Background? |
|---|---|---|
| Ticket inbox | 60s | No (default) |
| Model health | 60s | No |
| Training run in progress | 5s | Yes (`refetchIntervalInBackground: true`) |
| Pipeline run list | 30s | No |
| Universe list | On-demand only | Manual refresh button |

### Mutation Patterns

```typescript
// Optimistic update for simple mutations
const useMarkReviewed = () =>
  useMutation({
    mutationFn: (ticketId: string) =>
      apiClient.patch(`/api/v1/tickets/${ticketId}`, { status: "REVIEWED" }),
    onMutate: async (ticketId) => {
      await queryClient.cancelQueries({ queryKey: ticketKeys.all });
      const previous = queryClient.getQueryData(ticketKeys.all);
      queryClient.setQueryData(ticketKeys.all, (old) =>
        old?.map((t) => (t.id === ticketId ? { ...t, status: "REVIEWED" } : t))
      );
      return { previous };
    },
    onError: (_err, _id, context) => {
      queryClient.setQueryData(ticketKeys.all, context?.previous);
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ticketKeys.all });
    },
  });
```

---

## 6. State Management Rules

| Data type | Where it lives | Tool |
|---|---|---|
| Server data (universes, tickets, predictions) | TanStack Query cache | TanStack Query v5 |
| Auth state (JWT, user info) | Zustand store (memory only) | Zustand 4.x |
| Transient UI state (modals, filters) | Zustand store | Zustand 4.x |
| Form state | React Hook Form | RHF 7.x |

**Never**:
- Put server data in Zustand — TanStack Query owns it
- Store JWT in localStorage — memory only (Zustand slice)
- Duplicate data between stores — one source of truth per data type

---

## 7. API Client Conventions

### Central Fetch Wrapper

```typescript
// core/api-client.ts
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

class ApiClient {
  private getAuthHeader(): Record<string, string> {
    const token = useAuthStore.getState().accessToken;
    return token ? { Authorization: `Bearer ${token}` } : {};
  }

  async get<T>(path: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: { ...this.getAuthHeader(), ...options?.headers },
    });
    if (res.status === 401) {
      useAuthStore.getState().logout();
      window.location.href = "/login";
      throw new ApiError("SESSION_EXPIRED", "Session expired. Please log in again.");
    }
    if (!res.ok) {
      const err = await res.json();
      throw new ApiError(err.error_code, err.message, err.details);
    }
    return res.json();
  }

  // post, patch, delete follow same pattern
}
export const apiClient = new ApiClient();
```

### Error Handling

```typescript
class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly details?: Record<string, unknown>
  ) {
    super(message);
    this.name = "ApiError";
  }
}
```

All API errors use the backend's standard envelope: `{error_code, message, details, request_id}`.

### Type Generation

```bash
make gen-api  # Runs: openapi-typescript http://localhost:8000/openapi.json -o src/core/types/api.ts
```

Run after backend schema changes. Types in `src/core/types/api.ts` are auto-generated — **never edit manually**.

---

## 8. Testing Conventions

### Unit/Component Tests

- **Colocated**: `ComponentName.test.tsx` next to `ComponentName.tsx`
- **Framework**: vitest + @testing-library/react + @testing-library/jest-dom
- **Test user behavior**, not implementation details
- **Mock API calls** via MSW (Mock Service Worker) or TanStack Query test utilities

```typescript
// Example test structure
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { LoginPage } from "./LoginPage";

describe("LoginPage", () => {
  it("shows error on invalid credentials", async () => {
    render(<LoginPage />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Email"), "admin@example.com");
    await user.type(screen.getByLabelText("Password"), "wrong");
    await user.click(screen.getByRole("button", { name: /log in/i }));
    await waitFor(() => {
      expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument();
    });
  });
});
```

### E2E Tests

- **Framework**: Playwright
- **Location**: `e2e/` at repo root
- **Scope**: Critical paths only (login, create universe, view tickets)
- **Wait strategy**: Always wait on `GET /ready` returning 200 before running tests
- **Deterministic**: Seed DB before each run

### Quality Commands (Run BEFORE Committing)

```bash
pnpm lint       # ESLint
pnpm typecheck  # tsc --noEmit
pnpm test       # vitest run
```

---

## 9. Quality Checks (Reference: /react-doctor skill)

Before committing React code, run `/react-doctor` or manually check:

1. **Lint**: `pnpm lint` — zero errors
2. **TypeCheck**: `pnpm typecheck` — zero errors
3. **Tests**: `pnpm test` — all pass
4. **Dead code**: No unused imports, variables, or exports
5. **Accessibility**: All interactive elements keyboard-navigable, ARIA labels present
6. **Bundle size**: No regression (check with `pnpm build` and compare output)
7. **No console.log**: Search for console.log/console.warn in production code
8. **No commented-out code**: Delete it

---

## 10. Chart Conventions

### Financial Charts

- **Use TradingView Lightweight Charts** for: candlestick/OHLCV, line charts with crosshair, price scales
- MIT license, ~45 KB gzipped
- Consistent dark theme (prepare for future dark mode)

### General Charts

- **Use Recharts** for: training loss curves, conformal coverage history, feature drift indicators, backtest equity curves
- Simpler API than TradingView for non-financial data

### Chart Rules

1. Consistent color palette from Tailwind theme
2. Responsive by default (use container queries or ResizeObserver)
3. Accessible: provide aria-label describing the chart content
4. Loading state: skeleton or spinner while data fetches
5. Empty state: meaningful message when no data available

---

## 11. Accessibility

1. **All interactive elements keyboard-navigable** — tab order follows visual layout
2. **ARIA labels** on custom components (dialogs, dropdowns, tables)
3. **Color contrast ≥ 4.5:1** for text (WCAG AA)
4. **Focus management** on modal open/close — trap focus inside, restore on close
5. **Form errors** associated with fields via `aria-describedby`
6. **Skip-to-content link** for keyboard users
7. **Reduced motion**: Respect `prefers-reduced-motion` for animations

---

## 12. Performance

1. **Lazy-load routes** via `React.lazy` + `Suspense`:
```typescript
const UniverseListPage = lazy(() => import("./features/universes/pages/UniverseListPage"));
```
2. **Memoize expensive computations** only when profiled — don't premature optimize
3. **Virtualize long lists** (TanStack Virtual) for ticket inbox if > 100 items visible
4. **Debounce search inputs** (300ms default)
5. **Image optimization**: Use `loading="lazy"` on images; WebP format preferred
6. **Bundle analysis**: Run `pnpm build` and check output sizes. Alert if chunk > 200 KB.

---

## 13. shadcn/ui Conventions

- Components copied into `shared/components/ui/` (not imported from a package)
- Modify only when necessary for project-specific styling
- Use `cn()` utility from `shared/utils/cn.ts` for class merging
- Prefer shadcn primitives over building custom UI from scratch
- Available: Button, Dialog, AlertDialog, Table, Form, Input, Label, Select, Toast, Tabs, Card, Badge, Skeleton, etc.

---

## 14. Environment Variables

```bash
VITE_API_BASE_URL=http://localhost:8000  # Backend API base URL
```

All env vars must be prefixed with `VITE_` for Vite to expose them. Never put secrets in `VITE_` vars — they're embedded in the client bundle.

---

## 15. Future Considerations

- **Dark mode**: Structure CSS with CSS variables (shadcn already does this). Toggle via class on `<html>`.
- **i18n**: Deferred for v1. Keep user-facing strings in components (not extracted yet).
- **PWA/offline**: Deferred. The app requires a live backend connection.
- **Mobile responsive**: Design for desktop-first (this is a trading dashboard). Responsive breakpoints for tablet, but phone is not a target.
