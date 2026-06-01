# E2E Tests — Oracle Engine

Playwright end-to-end tests for the walking-skeleton critical path.

## Prerequisites

- Backend running on `http://localhost:8000` (seeded with admin + S&P 500 universe)
- Frontend running on `http://localhost:5173`

Start both with `make dev` from the repo root.

## Run locally

```bash
cd e2e
pnpm install
npx playwright install chromium
npx playwright test
```

## Configuration

| Env var | Default | Description |
|---|---|---|
| `BASE_URL` | `http://localhost:5173` | Frontend URL |
| `API_URL` | `http://localhost:8000` | Backend API URL |

## Test scope

`walking-skeleton.spec.ts` — the one critical-path test:
1. Navigate to `/` → redirect to `/login`
2. Log in as admin
3. Verify `/universes` shows "S&P 500"

Additional tests are added as features are built out.
