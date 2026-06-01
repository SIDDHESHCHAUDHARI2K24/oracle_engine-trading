# MBI Labs Oracle Engine — Claude Code Instructions

## 1. Project Overview

MBI Labs Oracle Engine is a self-improving research-grade ML pipeline that:
- Ingests OHLCV + macroeconomic data across multiple equity universes
- Engineers a 31-dimensional feature tensor per ticker per day
- Trains a Bi-LSTM and a Temporal Fusion Transformer Quad-Array per universe
- Calibrates predictions with locally-weighted split conformal prediction
- Validates via four backtest strategies
- Emits filtered Conviction Tickets for human review

**Current scope**: Pipeline A — the Deep Learning Math Engine. Pipeline B (LLM Agent Swarm, Fusion Engine, paper-trading sandbox) is explicitly out of scope for v1.

## 2. Tech Stack

### Backend
- Python 3.12+ | FastAPI 0.115.x | SQLAlchemy 2.0 async + asyncpg | PostgreSQL 16 + TimescaleDB
- PyTorch 2.2+ | pytorch-lightning 2.1.x+ | pytorch-forecasting 1.0.x+
- TA-Lib 0.4.28+ (pandas-ta as fallback) | vectorbt 0.25.x | scipy 1.11.x+
- Alembic 1.13.x (migrations) | uv (package mgmt) | ruff (lint/format)
- Prefect 3 (orchestration) | stdlib logging + JSON formatter | tenacity (retries)
- pytest + pytest-asyncio + testcontainers (testing)

### Frontend
- Vite 5.x | React 18.x | TypeScript 5.5+ (strict mode)
- React Router v6 | TanStack Query v5 | TanStack Table v8
- React Hook Form + Zod | Tailwind CSS 3.4+ | shadcn/ui
- TradingView Lightweight Charts 4.x | Recharts 2.x | Zustand 4.x
- vitest + @testing-library/react | Playwright (E2E) | pnpm

## 3. Repository Architecture

```
mbi-labs/
├── backend/
│   ├── alembic/
│   ├── pyproject.toml (uv)
│   ├── scripts/ (typer CLIs)
│   └── src/backend/
│       ├── main.py
│       ├── core/ (db, settings, logging, scheduler, security, artifact_store)
│       ├── features/
│       │   ├── auth/
│       │   ├── universes/
│       │   ├── data_ingestion/          # Block A1
│       │   ├── feature_engineering/     # Blocks A2 + A3
│       │   ├── ml_models/               # Blocks A4 + A5 + A6
│       │   ├── backtesting/             # Block A7
│       │   ├── conviction_tickets/      # Block A8 + scoring
│       │   └── monitoring/
│       └── orchestration/               # Prefect flows
└── frontend/
    └── src/
        ├── core/ (api-client, query-client, auth-context, types)
        ├── features/ (mirrors backend feature names)
        └── shared/ (components, utils, hooks)
```

## 4. Agent Tooling

### Obra Superpowers

This repo uses the **superpowers** agentic skills framework. Key rules:

1. **TDD is mandatory**. Write the test first. Watch it fail (RED). Then implement (GREEN). Then refactor. No exceptions.
2. **Spec → Plan → Execute**. Never jump straight to code.
3. **Evidence before claims**. Run the command, read the output, then make the claim.
4. **Subagent-driven development**. Fresh subagent per task with two-stage review.
5. **Systematic debugging**. No fixes without root cause investigation first.

Available skills (invoke when relevant):
- `writing-plans` — for multi-step tasks before touching code
- `subagent-driven-development` — for executing plans with independent tasks
- `systematic-debugging` — for any bug, test failure, or unexpected behavior
- `verification-before-completion` — before claiming work is done
- `requesting-code-review` — after completing features

### Graphify — Query-First Search

This repo uses **graphify** to build a knowledge graph. Query graphify BEFORE falling back to standard search:

1. **First**: Use graphify MCP tools (`query_graph`, `get_node`, `get_neighbors`, `shortest_path`, `get_community`)
2. **Then**: Traverse relationships to find what you need
3. **Fallback**: Only if graphify doesn't find it, use standard grep/glob/read

The graph auto-rebuilds on every git commit. Manual rebuild: `graphify update .`

## 5. Cross-Cutting Conventions

- **TDD mandatory**: RED → GREEN → REFACTOR
- **Evidence before claims**: Run it, read it, claim it
- **Stdlib JSON logging**: `logging` module + `JsonFormatter` (`backend/app/features/core/observability/logging.py`). Fields: `ts`, `level`, `event`, `request_id`, `service`. Never log secrets.
- **Standard API error envelope**: `{error_code, message, details, request_id}`
- **Soft-delete pattern**: `deleted_at TIMESTAMPTZ NULL`. Default: `WHERE deleted_at IS NULL`
- **Repository abstraction**: Per-feature `repository.py`. No raw SQL in services.
- **Pydantic v2**: `ConfigDict(from_attributes=True)` — NOT `orm_mode = True`
- **Async SQLAlchemy 2.0**: `AsyncSession` over `asyncpg`. Alembic uses sync engine.
- **API versioning**: All endpoints under `/api/v1/`
- **JWT auth**: Access (24h) in memory. Refresh (30d) in `HttpOnly Secure SameSite=Strict` cookie.
- **Polling everywhere**: No SSE/WebSockets in v1.

## 6. Pipeline-Specific Instructions — MUST READ

Read these before working on any feature:

- @agent-instructions/Pipeline-A-Agent-Instructions.md — Pipeline A backend: 9 features, locked decisions, spec deviations, data model, implementation notes
- @agent-instructions/Frontend-Agent-Instructions.md — Frontend: TypeScript strict, React conventions, TanStack Query patterns, testing, accessibility

## 7. Future Pipeline References

<!-- Future: @agent-instructions/Pipeline-B-Agent-Instructions.md -->

---

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)
