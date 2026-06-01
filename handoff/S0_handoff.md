# S0 Walking-Skeleton — Handoff Document

> **Status:** S0 is **~70% complete**. Backend walking-skeleton (T6 + T7) is live and verified end-to-end. Frontend scaffold (T8) and CI/E2E (T9) remain.

---

## 1. Goal (from `features-to-develop/development-plan-S0.md`)

Ship the smallest possible full-stack slice that proves the architecture:

- **Backend boots** → `/health` 200, `/ready` 200 with DB
- **Admin can log in** → JWT issued, refresh cookie set
- **Seeded universe is fetchable** → `GET /api/v1/universes` returns S&P 500
- **Frontend can log in** and display the universe
- **CI runs** backend + frontend tests on PR

This proves the loop: schema → migration → seed → API → frontend → E2E.

---

## 2. What is DONE (4 commits ahead of `5aadd6d`)

| SHA | Title | Notes |
|---|---|---|
| `5aadd6d` | S0 foundations | Monorepo scaffold, backend skeleton, Postgres+TimescaleDB (port 5433), MinIO, Alembic initial migration (5 tables), artifact store, health/ready |
| `cd15493` | **Replace loguru with stdlib logging + JSON formatter** | See §3 for why |
| `48f65af` | **Auth: JWT login/refresh/logout/me + admin seed** | argon2, HS256, 24h access + 30d sliding refresh, HttpOnly cookie |
| `aa1c7ec` | **Universes: list + detail API + S&P 500 seed** | `GET /api/v1/universes` and `GET /api/v1/universes/{id}`, both require Bearer token |

**Verified end-to-end live** (before this doc was written):

```
POST /auth/login              → 200, {access_token, user}            (564ms total)
GET  /api/v1/universes        → 200, {universes:[S&P 500], total:1}
```

---

## 3. Key Decisions Made This Session

### 3.1 Logging: loguru REMOVED, stdlib + JSON IN

**Why:** We initially added `loguru` for "structured JSON logging" — a 1.1KB blob per line, with a custom patcher, stdlib `InterceptHandler`, and a Windows cp1252 UTF-8 wrapper. We investigated this as a "boot is slow" candidate, but root-cause analysis showed the server actually boots in **3ms** and was never the problem (see §4).

**However, the change is kept** because it is objectively better:

| | loguru | stdlib + JSON formatter |
|---|---|---|
| Extra dep | `loguru>=0.7.3` (60KB) + `win32-setctime` | None (stdlib `logging`) |
| Output per line | 1.1KB JSON blob (click internals exposed) | ~150 bytes single-line JSON |
| Windows UTF-8 workaround | Required (`_wrap_stdout()`) | Not needed |
| Required fields (`ts, level, event, request_id, service`) | ✅ | ✅ |
| Test coverage | None | 4 unit tests for `JsonFormatter` |

**Implementation:** `backend/app/features/core/observability/logging.py` is 30 lines. `request_id_var: ContextVar` is shared with `RequestIdMiddleware` (just docstring references updated).

### 3.2 Makefile: `make dev` no longer uses `--reload`

**Why:** With `--reload`, every code change spawns a watcher process, doubling process count and adding file-watcher overhead. For S0 verification we restart manually when code changes — but a developer iterating on a single file benefits from reload.

**New targets:**
- `make dev` — MinIO + backend (no reload) + frontend. **Fastest cold boot.**
- `make dev-watch` — same as above but with `--reload` on the backend. **Use during iteration.**

### 3.3 Auth: JSON body login (not `OAuth2PasswordRequestForm`)

**Why:** Simpler for the frontend. `OAuth2PasswordRequestForm` requires form-encoded data + `python-multipart`; JSON is one-liner from `fetch`.

**Cookie config:** `refresh_token` set with `HttpOnly=True, Secure=True, SameSite=Strict, Max-Age=30d`.

### 3.4 Universes API: hard auth, soft 404

- Both list and detail require `Depends(get_current_user)` — i.e. Bearer token must be valid.
- Missing universe returns `404 {error_code: "UNIVERSE_NOT_FOUND", message: ...}` matching the project's standard error envelope (`{error_code, message, details?, request_id?}`).
- Eager-loads `memberships.ticker` on detail to avoid N+1.

### 3.5 Server lifecycle across turns

Per session: **start once, verify, kill only when code changes require restart.** No more 5-command ritual per turn. Verification = one `iwr` call + read `stdout.log` last lines.

---

## 4. The actual "boot is slow" issue (for the record)

**The server never was slow.** Evidence (from this session):

| Check | Time | Source |
|---|---|---|
| uvicorn process start → "Uvicorn running on..." | **3ms** | `stdout.log` line 1 vs line 4 timestamps |
| `/health` first call | 414ms | PowerShell `iwr` |
| `/ready` with DB | 418ms | PowerShell `iwr` |
| Login + universes (2 API calls) | 564ms | Combined |

**What was slow:**
1. PowerShell `Invoke-WebRequest` defaults to a 2-second timeout. When we tested the wrong port or before the bind, those 2.1s responses were **timeouts, not slow responses** — we were reading them as if the server was slow.
2. We were killing and respawning the server every turn (5+ bash calls × 5-30s = 30-150s per turn overhead).
3. Ghost processes from previous turns left port 8000 listening on a dead process.

**Lesson:** Trust the timestamps in the actual log, not the time PowerShell reports when a request fails. And keep the server running across turns.

---

## 5. What REMAINS (T8 + T9)

### T8 — Frontend walking-skeleton

**Scope:** Vite + React 18 + TypeScript strict + Tailwind + shadcn + React Router v6 + TanStack Query v5 + Zustand.

**Files to create:**

```
frontend/
├── package.json
├── pnpm-lock.yaml
├── vite.config.ts
├── tsconfig.json + tsconfig.node.json
├── tailwind.config.ts
├── postcss.config.js
├── index.html
├── components.json (shadcn)
├── .env.example                    (VITE_API_URL=http://localhost:8000)
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── index.css
    ├── core/
    │   ├── api-client.ts           (fetch wrapper with auth header injection)
    │   ├── query-client.ts         (TanStack Query client)
    │   ├── auth-context.tsx        (current user, login, logout, refresh)
    │   └── types.ts                (TS types matching backend schemas)
    ├── features/
    │   ├── auth/
    │   │   ├── LoginPage.tsx       (email + password form, shadcn)
    │   │   ├── useLogin.ts         (TanStack Query mutation)
    │   │   └── store.ts            (Zustand access token in memory)
    │   └── universes/
    │       ├── UniverseListPage.tsx
    │       └── useUniverses.ts     (TanStack Query hook)
    └── shared/
        └── components/
            └── ui/                 (shadcn components: button, input, card)
```

**Acceptance:**
- `pnpm dev` boots Vite on `http://localhost:5173`
- Login page renders at `/login`
- Submitting valid creds stores JWT in Zustand, navigates to `/universes`
- `/universes` page shows "S&P 500" universe (no real auth persistence needed in S0 — Zustand clears on refresh)
- `pnpm build` succeeds; `pnpm lint` clean
- `pnpm test` passes (vitest unit tests for at least one hook + one component)

**Generate types:** `make gen-api` runs `openapi-typescript http://localhost:8000/openapi.json -o src/core/types/api.ts`.

### T9 — CI + E2E + pre-commit + features.md

**Scope:** GitHub Actions for backend + frontend tests; one Playwright E2E test for the walking-skeleton loop; pre-commit hooks; per-feature `features.md` summaries.

**Files to create:**

```
.github/
└── workflows/
    ├── test-backend.yml           (uv sync, pytest, ruff check)
    ├── test-frontend.yml          (pnpm install, vitest, eslint, build)
    └── e2e.yml                    (matrix: backend + frontend + playwright)
e2e/
├── package.json
├── playwright.config.ts
├── tests/
│   └── walking-skeleton.spec.ts   (login → see S&P 500)
└── README.md
.pre-commit-config.yaml            (ruff, prettier, basic file checks)
backend/app/features/core/features.md
backend/app/features/auth/features.md
backend/app/features/universes/features.md
frontend/src/features/auth/feature.md
frontend/src/features/universes/feature.md
```

**Acceptance:**
- All 3 workflows valid YAML
- `e2e/tests/walking-skeleton.spec.ts` runs locally with `npx playwright test` and passes against a running stack
- `pre-commit run --all-files` runs clean on the current tree
- Each `features.md` summarizes the feature per the project's `feature.md` convention

---

## 6. Known issues / gotchas for whoever resumes

| Issue | Resolution |
|---|---|
| Port 5432 occupied by native Postgres (PID 7364) | Docker TimescaleDB uses port **5433**. Update `.env` `DATABASE_URL` accordingly. |
| Native Postgres on 5432 has `mbi_user/mbi_password` — **do not** connect there | Always use `localhost:5433` for `mbi` and `localhost:5432` is unrelated |
| `psycopg2-binary` is the sync driver (Alembic needs it); `asyncpg` is the async driver (runtime needs it) | Both are in `pyproject.toml`; URLs use `postgresql+asyncpg://` for app, `postgresql+psycopg2://` for Alembic |
| `Makefile` uses `grep` + `awk` for help — works on Git Bash but not pure PowerShell | Run `make help` from Git Bash or WSL; PowerShell users get a partial help screen |
| `git` post-commit hook calls `graphify update .` (background) — produces `null byte` warning | Harmless; graph rebuilds in background. To silence, `rm .git/hooks/post-commit` |
| `uv` wrapper cost (~200ms) on every `uv run ...` | Acceptable for now; revisit if test suite hits this |
| Server has `--reload` OFF in `make dev` | Restart manually after code changes (`Stop-Process -Id <pid>` then re-start) OR use `make dev-watch` |

---

## 7. How to resume (checklist)

1. **Check server state:** `Get-NetTCPConnection -State Listen -LocalPort 8000`. If bound, the server is alive.
2. **If you need to start fresh:**
   ```powershell
   cd C:\Projects\Oracle Engine - Trading\backend
   uv run uvicorn app.app:create_app --factory --loop asyncio --host 127.0.0.1 --port 8000
   ```
3. **If you need to run migrations:** `make migrate` (or `cd backend && uv run alembic upgrade head`).
4. **If you need seed data:**
   ```bash
   cd backend
   uv run python scripts/seed_admin.py        # idempotent
   uv run python scripts/seed_universes.py    # idempotent
   ```
5. **Verify health:** `iwr http://127.0.0.1:8000/health` → 200; `iwr http://127.0.0.1:8000/ready` → 200 with `db:1`.
6. **Run all tests:** `make test-backend` (and `make test-frontend` once T8 lands).
7. **Pick up T8** — see §5. Use subagent for parallel work (frontend scaffold while doing something else is fine).
8. **Pick up T9** — see §5. T9 is independent of T8.

---

## 8. Reference: commit log

```
aa1c7ec  feat(universes): list + detail API + S&P 500 seed
48f65af  feat(auth): JWT login, refresh, logout, me endpoints + admin seed
cd15493  chore: replace loguru with stdlib logging + JSON formatter
5aadd6d  feat: S0 foundations — monorepo scaffold, backend skeleton, Postgres+TimescaleDB,
         MinIO, Alembic with initial migration (users, sessions, universes, tickers,
         universe_memberships), artifact store, loguru structured logging, health/ready
a5e4bd1  chore: pre-development setup — agent instructions, graphify, superpowers
```

---

## 9. Reference: file map (created this session)

```
backend/
├── pyproject.toml                                    (modified: -loguru, +argon2/jose/typer/multipart)
├── uv.lock                                           (regenerated)
├── app/
│   ├── app.py                                        (modified: +universes_router)
│   └── features/
│       ├── core/
│       │   ├── observability/
│       │   │   ├── logging.py                        (rewritten: loguru→stdlib, 30 lines)
│       │   │   └── middleware.py                     (docstring only)
│       │   └── tests/
│       │       └── test_logging.py                   (new: 4 tests)
│       ├── auth/
│       │   ├── service.py                            (new: argon2 + JWT + token rotation)
│       │   ├── repository.py                         (new: User/Session CRUD)
│       │   ├── dependencies.py                       (new: get_current_user, requires_role)
│       │   ├── schemas.py                            (new: LoginRequest, TokenResponse, UserResponse)
│       │   ├── routers.py                            (modified: wires endpoints)
│       │   └── endpoints/
│       │       ├── login.py                          (modified: JSON body login)
│       │       ├── logout.py                         (modified: stdlib logger)
│       │       ├── me.py                             (modified: simple)
│       │       └── refresh.py                        (new: token rotation)
│       └── universes/
│           ├── repository.py                         (new)
│           ├── schemas.py                            (new)
│           ├── service.py                            (new)
│           └── router.py                             (new)
├── scripts/
│   ├── seed_admin.py                                 (existing — confirmed working)
│   └── seed_universes.py                             (new: S&P 500 + 3 tickers)

Makefile                                              (modified: dev no-reload, +dev-watch)
.gitignore                                            (modified: ignore .log, .pid)
```

---

*Document last updated: end of session. Resumer: pick up at T8 (frontend scaffold).*
