# Pre-Development Setup — Handoff Document

> **Project**: MBI Labs Oracle Engine — Pipeline A
> **Status**: Approved plan, ready for implementation
> **Purpose**: This document contains everything a new coding session needs to execute the pre-development setup. No context from the planning session is required — all decisions, commands, file contents, and sequencing are self-contained here.

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Repository Current State](#2-repository-current-state)
3. [Deliverable 1 — Obra Superpowers Setup](#3-deliverable-1--obra-superpowers-setup)
4. [Deliverable 2 — Graphify CLI + MCP + Hooks Setup](#4-deliverable-2--graphify-cli--mcp--hooks-setup)
5. [Deliverable 3 — Top-Level Agent Instruction Files](#5-deliverable-3--top-level-agent-instruction-files)
6. [Deliverable 4 — Pipeline-A-Agent-Instructions.md](#6-deliverable-4--pipeline-a-agent-instructionsmd)
7. [Deliverable 5 — Frontend-Agent-Instructions.md](#7-deliverable-5--frontend-agent-instructionsmd)
8. [Complete File Manifest](#8-complete-file-manifest)
9. [Execution Order](#9-execution-order)
10. [Verification Checklist](#10-verification-checklist)
11. [Reference Documents](#11-reference-documents)

---

## 1. Executive Summary

This pre-development phase equips the Oracle Engine repo with 5 deliverables before any feature code is written:

| # | Deliverable | What It Does |
|---|---|---|
| D1 | Obra Superpowers | Installs the agentic skills + methodology framework (TDD enforcement, spec→plan→execute workflow, subagent-driven development, evidence-based verification) for Opencode, Claude Code, Cursor, and Codex |
| D2 | Graphify CLI + MCP + Hooks | Installs the knowledge-graph tool (71.5x fewer tokens per query vs raw files), MCP server for all agents, and git hooks for auto-rebuild on changes |
| D3 | AGENTS.md, CLAUDE.md, .cursorrules, codex-instructions.md | Top-level agent instruction files — the main source of truth, referencing pipeline-specific and frontend-specific instruction files |
| D4 | agent-instructions/Pipeline-A-Agent-Instructions.md | Pipeline A backend-specific instructions: 9 features, locked decisions, 12 spec deviations, data model, conventions |
| D5 | agent-instructions/Frontend-Agent-Instructions.md | Frontend-specific instructions: TypeScript strict, React conventions, TanStack Query patterns, testing, accessibility |

### Key Design Decision — Reference Pattern

Each top-level instruction file (AGENTS.md, CLAUDE.md, etc.) contains core project context and **explicitly references** pipeline-specific files:

```
→ agent-instructions/Pipeline-A-Agent-Instructions.md
→ agent-instructions/Frontend-Agent-Instructions.md
```

When Pipeline B arrives, we add one line to each top-level file:
```
→ agent-instructions/Pipeline-B-Agent-Instructions.md
```

No restructuring needed. The pipeline-specific files are self-contained.

---

## 2. Repository Current State

The repo at `C:\Projects\Oracle Engine - Trading` contains:

```
.
├── features-to-develop/
│   ├── development-plan-S0.md    (S0: Foundations — 9 tasks, 41 sub-tasks)
│   └── development-plan-S1.md    (S1: Auth & Universes — 8 tasks, 34 sub-tasks)
├── mbi-pipeline-a-v1-design.md   (Full Pipeline A design: 9 features, 1370 lines)
└── tech-stack-analysis.md        (Stack validation: 10 gaps, 20 assumptions, 15 compat notes)
```

No `AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `opencode.json`, `.gitignore`, or any agent configuration exists yet. This is a clean slate.

### Critical Reference Document Summaries

**mbi-pipeline-a-v1-design.md** — The full Pipeline A design document covering:
- 9 Features: Auth, Universes, Data Ingestion (Block A1), Feature Engineering (Blocks A2+A3), ML Models (Blocks A4+A5+A6), Backtesting (Block A7), Conviction Tickets (Block A8), Monitoring, Orchestration (Prefect)
- Tech Stack: FastAPI (Python 3.11+), SQLAlchemy 2.0 async + asyncpg, PostgreSQL 16 + TimescaleDB, PyTorch 2.2+, Prefect 3, Vite + React 18 + TypeScript strict
- 12 Locked Spec Deviations (LSTM uses HuberLoss not BCELoss, uncertainty-aware blending not 60/40, locally-weighted split conformal not isotonic regression, etc.)
- Repository Architecture: `backend/` + `frontend/` monorepo, feature-mirrored layout
- Master Data Model: 20+ tables across 9 features

**tech-stack-analysis.md** — Stack validation covering:
- 59 stack components with version targets
- Coverage assessment per feature
- 10 Gaps identified (TA-Lib system dep, conformal prediction custom impl, Prefect self-hosting, etc.)
- 20 Assumptions (ruff for backend, Pydantic v2, per-test-database via testcontainers, etc.)
- 15 Compatibility Notes (SQLAlchemy async + Alembic, TimescaleDB + Alembic autogen, yfinance reliability, etc.)

**development-plan-S0.md** — Stage S0 (Foundations/Walking Skeleton):
- 9 tasks, 41 sub-tasks, 8–12 dev days
- Repo scaffold, backend from boilerplate, Postgres+TimescaleDB, MinIO, Alembic first migration, auth skeleton (JWT over session store), universe seed, frontend skeleton, CI+E2E

**development-plan-S1.md** — Stage S1 (Auth & Universes Full Build):
- 8 tasks, 34 sub-tasks, 11–15 dev days
- Full account management, ticker registry + Alpaca sync, universe CRUD, time-aware membership + CSV import, ConstituentSource index seeding, universe UI, integration+E2E

---

## 3. Deliverable 1 — Obra Superpowers Setup

### What It Is

[obra/superpowers](https://github.com/obra/superpowers) (v5.1.0, MIT license) is an agentic skills framework that enforces:
- **TDD mandatory** — RED-GREEN-REFACTOR, no exceptions
- **Spec → Plan → Execute** workflow — agents never jump straight to code
- **Subagent-driven development** — fresh subagent per task, two-stage review
- **Evidence before claims** — run the command, read the output, then make the claim
- **Git worktree isolation** — feature work in isolated worktrees, never on main

Supports: Claude Code, Codex CLI/App, Cursor, OpenCode, Gemini CLI, GitHub Copilot CLI

### Step-by-Step Implementation

#### Step D1.1: Install superpowers for OpenCode

Create or update `opencode.json` at repo root with the superpowers plugin:

```json
{
  "plugin": ["superpowers@git+https://github.com/obra/superpowers.git"]
}
```

**Windows fallback** (if git-backed spec fails):
```powershell
npm install superpowers@git+https://github.com/obra/superpowers.git --prefix "$HOME\.config\opencode"
```
Then update `opencode.json`:
```json
{
  "plugin": ["~/.config/opencode/node_modules/superpowers"]
}
```

#### Step D1.2: Install superpowers for Claude Code

Option A (inside Claude Code session):
```
/plugin install superpowers@claude-plugins-official
```

Option B (manual — create the plugin directory structure):

Create `.claude-plugin/package.json`:
```json
{
  "name": "superpowers",
  "version": "5.1.0",
  "description": "Agentic skills framework for Claude Code",
  "type": "module"
}
```

The key bootstrap is the `using-superpowers` skill — it's the entry point that makes skills auto-trigger at session start. Without it, skills are "dead weight."

#### Step D1.3: Install superpowers for Cursor

Option A (inside Cursor):
```
/add-plugin superpowers
```

Option B (manual): Create `.cursor-plugin/` directory with the plugin manifest referencing the superpowers repo.

#### Step D1.4: Install superpowers for Codex

Install via Codex CLI or App plugin marketplace. Additionally, add `multi_agent = true` under `[features]` in `~/.codex/config.toml`.

#### Step D1.5: Verify superpowers is loaded

For each agent, start a session and verify that the `using-superpowers` skill auto-triggers. The agent should recognize skills like `writing-plans`, `subagent-driven-development`, `systematic-debugging`, `verification-before-completion`, etc.

### Files Created/Modified

| File | Action |
|---|---|
| `opencode.json` | Create or update (add superpowers plugin) |
| `.claude-plugin/` | Create directory (if manual install) |
| `.cursor-plugin/` | Create directory (if manual install) |
| `.codex-plugin/` | Create directory (if manual install) |

---

## 4. Deliverable 2 — Graphify CLI + MCP + Hooks Setup

### What It Is

[Graphify](https://github.com/safishamsi/graphify) (PyPI: `graphifyy` — double-y) turns any folder of files into a queryable knowledge graph:
- **71.5x fewer tokens per query** vs reading raw files
- 3-pass processing: (1) tree-sitter AST parsing (local, free), (2) audio/video transcription (local, free), (3) docs/papers/images (LLM-backed)
- Leiden algorithm community detection (no embeddings needed)
- Every edge tagged EXTRACTED/INFERRED/AMBIGUOUS with confidence scores

**CLI commands**: `graphify .`, `graphify query "question"`, `graphify path "A" "B"`, `graphify explain "X"`, `graphify hook install`

**MCP server** (10 tools, 6 resources): `query_graph`, `get_node`, `get_neighbors`, `get_community`, `god_nodes`, `graph_stats`, `shortest_path`, `list_prs`, `get_pr_impact`, `triage_prs`

### Step-by-Step Implementation

#### Step D2.1: Install graphify CLI

```bash
uv tool install graphifyy
```

Alternative:
```bash
pipx install graphifyy
# or
pip install graphifyy
```

Verify:
```bash
graphify --help
```

#### Step D2.2: Run initial graph build

```bash
cd "C:\Projects\Oracle Engine - Trading"
graphify . --update
```

This creates `graphify-out/` with:
- `graph.html` — Interactive vis.js visualization
- `graph.json` — Full graph in NetworkX node-link format
- `GRAPH_REPORT.md` — Highlights: god nodes, surprising connections, suggested questions
- `cache/` — SHA256 content-hash cache for incremental updates

#### Step D2.3: Install graphify for each coding agent (project-scoped)

**OpenCode**:
```bash
graphify install --project --platform opencode
```

**Claude Code (Windows)**:
```bash
graphify install --project --platform windows
```

**Cursor**:
```bash
graphify install --project --platform cursor
```

**Codex**:
```bash
graphify install --project --platform codex
```

The `--project` flag writes to the current repo (not user profile), so the whole team gets the skill. This creates:
- `.claude/skills/graphify/SKILL.md` (for Claude Code)
- `.agents/skills/graphify/SKILL.md` (for Codex)
- `.cursor/rules/` (for Cursor)
- Appropriate instruction files per platform

#### Step D2.4: Install git hooks for auto-rebuild on changes

```bash
graphify hook install
```

This creates:
- **post-commit hook**: Rebuilds the graph after every commit (AST-only for code, no API cost)
- **post-checkout hook**: Rebuilds after branch switches
- **git merge driver**: Auto union-merges `graph.json` so parallel commits never leave conflict markers

Verify:
```bash
graphify hook status
```

#### Step D2.5: Configure graphify MCP server for OpenCode

Add MCP server config to `opencode.json` (merge with superpowers plugin from D1.1):

```json
{
  "plugin": ["superpowers@git+https://github.com/obra/superpowers.git"],
  "mcpServers": {
    "graphify": {
      "command": "python",
      "args": ["-m", "graphify.serve", "graphify-out/graph.json"],
      "transport": "stdio"
    }
  }
}
```

#### Step D2.6: Configure graphify MCP server for Claude Code

Create `.mcp.json` at repo root:

```json
{
  "mcpServers": {
    "graphify": {
      "command": "python",
      "args": ["-m", "graphify.serve", "graphify-out/graph.json"]
    }
  }
}
```

#### Step D2.7: Configure graphify MCP server for Cursor

Create `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "graphify": {
      "command": "python",
      "args": ["-m", "graphify.serve", "graphify-out/graph.json"]
    }
  }
}
```

#### Step D2.8: Configure graphify MCP server for Codex

Add to Codex MCP configuration (project-level). Codex uses a similar MCP config pattern. Check the Codex docs for the exact file path, but typically this goes in `.codex/mcp.json` or the project's `codex.json`.

#### Step D2.9: Create .gitignore

Create `.gitignore` at repo root. Key entries:

```gitignore
# Graphify — commit graph.json for team use, ignore large/regenerable outputs
graphify-out/graph.html
graphify-out/GRAPH_REPORT.md
graphify-out/cache/
graphify-out/obsidian/
graphify-out/wiki/
graphify-out/converted/
# Keep graphify-out/graph.json tracked (committed for team)

# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
.venv/
*.egg
.pytest_cache/
.ruff_cache/
*.pt

# Node / Frontend
node_modules/
dist/
.vite/

# Environment & secrets
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Model artifacts
*.pt
*.pth

# Coverage
htmlcov/
.coverage
coverage.xml
```

#### Step D2.10: Verify everything works

```bash
# Verify CLI
graphify query "what is Pipeline A?"

# Verify hooks
graphify hook status

# Verify MCP server starts
python -m graphify.serve graphify-out/graph.json  # Should start and listen on stdio
```

### Files Created/Modified

| File | Action |
|---|---|
| `graphify-out/` | Generate (via `graphify .`) |
| `.claude/skills/graphify/SKILL.md` | Generate (via `graphify install --project`) |
| `.agents/skills/graphify/SKILL.md` | Generate (via `graphify install --project --platform codex`) |
| `.cursor/rules/` | Generate (via `graphify install --project --platform cursor`) |
| `.git/hooks/post-commit` | Generate (via `graphify hook install`) |
| `.git/hooks/post-checkout` | Generate (via `graphify hook install`) |
| `opencode.json` | Create or update (add graphify MCP server) |
| `.mcp.json` | Create (graphify MCP for Claude Code) |
| `.cursor/mcp.json` | Create (graphify MCP for Cursor) |
| `.gitignore` | Create |

---

## 5. Deliverable 3 — Top-Level Agent Instruction Files

### Design Principle

Each top-level file contains the **same core content** but formatted for its specific agent platform. They all reference the pipeline-specific and frontend-specific instruction files. When a new pipeline arrives, we add one reference line — no restructuring.

### Content Structure (Common to All Four Files)

Each file must contain these sections:

```
1. Project Overview — MBI Labs Oracle Engine, Pipeline A
2. Tech Stack Summary (backend + frontend)
3. Repository Architecture (directory tree from design §13)
4. Agent Tooling Setup
   - Obra Superpowers: how to invoke skills, mandatory workflow
   - Graphify: query-first search pattern, fallback to standard search
5. Cross-Cutting Conventions
   - TDD is mandatory (RED-GREEN-REFACTOR)
   - Evidence before claims
   - Loguru structured logging
   - Standard API error envelope
   - Soft-delete pattern
   - Repository abstraction pattern
6. Pipeline-Specific Instructions — MUST READ
   → agent-instructions/Pipeline-A-Agent-Instructions.md
   → agent-instructions/Frontend-Agent-Instructions.md
7. Future Pipeline References (placeholder for Pipeline B, C, etc.)
```

### File: AGENTS.md

Target: Codex + generic agents. Standard markdown format.

**Create** `AGENTS.md` at repo root with the following content:

```markdown
# MBI Labs Oracle Engine — Agent Instructions

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
- Python 3.11+ | FastAPI 0.115.x | SQLAlchemy 2.0 async + asyncpg | PostgreSQL 16 + TimescaleDB
- PyTorch 2.2+ | pytorch-lightning 2.1.x+ | pytorch-forecasting 1.0.x+
- TA-Lib 0.4.28+ (pandas-ta as fallback) | vectorbt 0.25.x | scipy 1.11.x+
- Alembic 1.13.x (migrations) | uv (package mgmt) | ruff (lint/format)
- Prefect 3 (orchestration) | loguru (logging) | tenacity (retries)
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
│       │   ├── data_ingestion/     # Block A1
│       │   ├── feature_engineering/ # Blocks A2 + A3
│       │   ├── ml_models/          # Blocks A4 + A5 + A6
│       │   ├── backtesting/        # Block A7
│       │   ├── conviction_tickets/ # Block A8 + scoring
│       │   └── monitoring/
│       └── orchestration/          # Prefect flows
└── frontend/
    └── src/
        ├── core/ (api-client, query-client, auth-context, types)
        ├── features/ (mirrors backend feature names)
        └── shared/ (components, utils, hooks)
```

Each backend feature has: `models.py`, `schemas.py`, `repository.py`, `service.py`, `dependencies.py`, `router.py`, `endpoints/`, `tests/`, `features.md`

## 4. Agent Tooling

### Obra Superpowers

This repo uses the **superpowers** agentic skills framework. Key rules:

1. **TDD is mandatory**. Write the test first. Watch it fail (RED). Then implement (GREEN). Then refactor. No exceptions.
2. **Spec → Plan → Execute**. Never jump straight to code. Produce a spec, get approval, then plan, then execute.
3. **Evidence before claims**. Never say "it works" without running the verification command and showing output.
4. **Subagent-driven development**. Fresh subagent per task with two-stage review.
5. **Systematic debugging**. No fixes without root cause investigation first. If 3+ fixes fail, question the architecture.

Available skills (invoke when relevant, even if only 1% chance):
- `writing-plans` — for multi-step tasks before touching code
- `subagent-driven-development` — for executing plans with independent tasks
- `systematic-debugging` — for any bug, test failure, or unexpected behavior
- `verification-before-completion` — before claiming work is done
- `requesting-code-review` — after completing features

### Graphify — Query-First Search

This repo uses **graphify** to build a knowledge graph from all files. Agents MUST use graphify before falling back to standard search:

1. **First**: Query the graphify MCP server or run `graphify query "your question"`
2. **Then**: Use `get_neighbors`, `shortest_path`, `get_community` to traverse relationships
3. **Fallback**: If graphify doesn't find what you need, use standard grep/glob/read tools

The graph is automatically rebuilt on every git commit (post-commit hook). For manual rebuild: `graphify . --update`

## 5. Cross-Cutting Conventions

- **TDD mandatory**: RED → GREEN → REFACTOR. Write test first, always.
- **Evidence before claims**: Run the command, read the output, then make the claim.
- **Loguru structured logging**: JSON to stdout. Required fields: `ts`, `level`, `request_id`, `event`. Never log secrets.
- **Standard API error envelope**: `{error_code, message, details, request_id}`. Machine-readable codes: `UNIVERSE_NOT_FOUND`, `TICKER_NOT_FOUND`, etc.
- **Soft-delete pattern**: `deleted_at TIMESTAMPTZ NULL`. Default queries filter `WHERE deleted_at IS NULL`. "Include deleted" toggle removes filter.
- **Repository abstraction**: Per-feature `repository.py` centralizes data access. No raw SQL in services. Future cache decoration is one place.
- **Pydantic v2**: `model_config = ConfigDict(from_attributes=True)` (NOT `orm_mode = True`).
- **Async SQLAlchemy 2.0**: `AsyncSession` over `asyncpg`. Alembic uses sync engine (convert async URL to sync in `env.py`).
- **API versioning**: All endpoints under `/api/v1/`.
- **JWT auth**: Access token (24h) in memory. Refresh token (30d sliding) in `HttpOnly Secure SameSite=Strict` cookie.
- **Polling everywhere**: No SSE/WebSockets/webhooks in v1. TanStack Query `refetchInterval` per surface.

## 6. Pipeline-Specific Instructions — MUST READ

The following files contain detailed, pipeline-specific implementation instructions. Read them before working on any feature:

- **[agent-instructions/Pipeline-A-Agent-Instructions.md](agent-instructions/Pipeline-A-Agent-Instructions.md)** — Pipeline A backend: 9 features, locked decisions, 12 spec deviations, data model, feature-by-feature implementation notes, compatibility notes, testing conventions, security conventions
- **[agent-instructions/Frontend-Agent-Instructions.md](agent-instructions/Frontend-Agent-Instructions.md)** — Frontend: TypeScript strict, React conventions, TanStack Query patterns, testing, accessibility, performance

## 7. Future Pipeline References

When new pipelines come online, their instruction files will be referenced here:

<!-- Future: → agent-instructions/Pipeline-B-Agent-Instructions.md -->
<!-- Future: → agent-instructions/Pipeline-C-Agent-Instructions.md -->
```

### File: CLAUDE.md

Target: Claude Code. Markdown with `@file` reference support. Same core content as AGENTS.md but with Claude-specific formatting.

**Create** `CLAUDE.md` at repo root with the following content:

```markdown
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
- Python 3.11+ | FastAPI 0.115.x | SQLAlchemy 2.0 async + asyncpg | PostgreSQL 16 + TimescaleDB
- PyTorch 2.2+ | pytorch-lightning 2.1.x+ | pytorch-forecasting 1.0.x+
- TA-Lib 0.4.28+ (pandas-ta as fallback) | vectorbt 0.25.x | scipy 1.11.x+
- Alembic 1.13.x (migrations) | uv (package mgmt) | ruff (lint/format)
- Prefect 3 (orchestration) | loguru (logging) | tenacity (retries)
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
│       │   ├── data_ingestion/     # Block A1
│       │   ├── feature_engineering/ # Blocks A2 + A3
│       │   ├── ml_models/          # Blocks A4 + A5 + A6
│       │   ├── backtesting/        # Block A7
│       │   ├── conviction_tickets/ # Block A8 + scoring
│       │   └── monitoring/
│       └── orchestration/          # Prefect flows
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

The graph auto-rebuilds on every git commit. Manual rebuild: `graphify . --update`

## 5. Cross-Cutting Conventions

- **TDD mandatory**: RED → GREEN → REFACTOR
- **Evidence before claims**: Run it, read it, claim it
- **Loguru structured logging**: JSON to stdout. Fields: `ts`, `level`, `request_id`, `event`. Never log secrets.
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
```

### File: .cursorrules

Target: Cursor. Plain text format (no markdown headers, simpler syntax).

**Create** `.cursorrules` at repo root with the following content:

```
MBI Labs Oracle Engine — Cursor Rules

PROJECT OVERVIEW
- Self-improving research-grade ML pipeline
- Pipeline A (current): Deep Learning Math Engine
- Pipeline B (future): LLM Agent Swarm, Fusion Engine, paper-trading sandbox
- Ingests OHLCV + macro → 31-dim feature tensor → Bi-LSTM + TFT Quad-Array per universe → conformal calibration → backtest validation → Conviction Tickets

TECH STACK
Backend: Python 3.11+ | FastAPI | SQLAlchemy 2.0 async + asyncpg | PostgreSQL 16 + TimescaleDB | PyTorch 2.2+ | pytorch-lightning | pytorch-forecasting | TA-Lib | vectorbt | Prefect 3 | loguru | ruff | uv | pytest + testcontainers
Frontend: Vite | React 18 | TypeScript strict | React Router v6 | TanStack Query v5 | TanStack Table v8 | React Hook Form + Zod | Tailwind + shadcn/ui | TradingView Lightweight Charts | Recharts | Zustand | vitest | Playwright | pnpm

REPO ARCHITECTURE
backend/alembic/ — migrations
backend/scripts/ — typer CLIs
backend/src/backend/core/ — db, settings, logging, scheduler, security, artifact_store
backend/src/backend/features/ — auth, universes, data_ingestion, feature_engineering, ml_models, backtesting, conviction_tickets, monitoring
backend/src/backend/orchestration/ — Prefect flows
frontend/src/core/ — api-client, query-client, auth-context, types
frontend/src/features/ — mirrors backend feature names
frontend/src/shared/ — components (shadcn), utils, hooks

AGENT TOOLING
- Obra Superpowers: TDD mandatory, spec→plan→execute, evidence before claims, subagent-driven development
- Graphify: Query knowledge graph FIRST (graphify query, get_neighbors, shortest_path). Fallback to grep/glob/read only if graphify fails.

MANDATORY CONVENTIONS
- TDD: Write test first (RED), implement (GREEN), refactor. No exceptions.
- Evidence: Run command, read output, then claim. Never "should work."
- Loguru: JSON to stdout. Fields: ts, level, request_id, event. No secrets in logs.
- Error envelope: {error_code, message, details, request_id}
- Soft-delete: deleted_at column. Default: WHERE deleted_at IS NULL.
- Repository pattern: Per-feature repository.py. No raw SQL in services.
- Pydantic v2: ConfigDict(from_attributes=True), NOT orm_mode
- SQLAlchemy async: AsyncSession + asyncpg. Alembic uses sync engine.
- API prefix: /api/v1/
- JWT: Access (24h) in memory. Refresh (30d) in HttpOnly Secure SameSite=Strict cookie.
- Polling: No SSE/WebSockets in v1. TanStack Query refetchInterval.

PIPELINE-SPECIFIC INSTRUCTIONS — READ BEFORE CODING
→ agent-instructions/Pipeline-A-Agent-Instructions.md (backend: 9 features, locked decisions, data model, conventions)
→ agent-instructions/Frontend-Agent-Instructions.md (frontend: TypeScript strict, React patterns, testing, accessibility)

FUTURE PIPELINES
→ (Placeholder for Pipeline-B-Agent-Instructions.md)
```

### File: codex-instructions.md

Target: Codex. Standard markdown, similar to AGENTS.md.

**Create** `codex-instructions.md` at repo root with the same content as AGENTS.md. The content is identical to AGENTS.md since Codex reads standard markdown. Copy the AGENTS.md content verbatim.

---

## 6. Deliverable 4 — Pipeline-A-Agent-Instructions.md

### File Location

`agent-instructions/Pipeline-A-Agent-Instructions.md`

### Create the directory first

```bash
mkdir -p "C:\Projects\Oracle Engine - Trading\agent-instructions"
```

### Full File Content

```markdown
# Pipeline A — Agent Instructions (Backend)

> **Scope**: Pipeline A — the Deep Learning Math Engine. A self-improving research-grade ML pipeline.
> **Companion docs**: `mbi-pipeline-a-v1-design.md`, `tech-stack-analysis.md`
> **For frontend instructions**: See `agent-instructions/Frontend-Agent-Instructions.md`

---

## 1. Pipeline A Overview

Pipeline A is a self-improving research-grade ML pipeline that:
1. Ingests OHLCV + macroeconomic data across multiple equity universes (Block A1)
2. Engineers a 31-dimensional feature tensor per ticker per day (Blocks A2 + A3)
3. Trains a Bi-LSTM and a Temporal Fusion Transformer Quad-Array per universe (Blocks A4 + A5)
4. Blends ensemble predictions with uncertainty-aware weighting (Block A6)
5. Calibrates with locally-weighted split conformal prediction (Block A6)
6. Validates via four backtest strategies (Block A7)
7. Emits filtered Conviction Tickets for human review (Block A8)
8. Monitors model health, conformal coverage, feature drift (Feature 8)
9. Orchestrates daily/weekly flows via Prefect (Feature 9)

### 9 Features Summary

| # | Feature | Spec Block | Key Artifact |
|---|---|---|---|
| 1 | Auth & User Accounts | — | JWT + session-backed refresh |
| 2 | Universe Management | — | Time-aware ticker baskets |
| 3 | Data Ingestion | A1 | OHLCV + macro in TimescaleDB |
| 4 | Feature Engineering | A2 + A3 | 31-dim feature matrix + 4-horizon targets |
| 5 | ML Models | A4 + A5 + A6 | 1 LSTM + 4 TFTs + conformal per universe |
| 6 | Backtesting | A7 | 4 strategies × 6 metrics, filter gate |
| 7 | Conviction Tickets | A8 | Risk-adjusted score, filter gate, lifecycle |
| 8 | Monitoring & Model Health | — | Coverage, drift, loss curves, alerts |
| 9 | Orchestration | — | 7 Prefect flows on cron schedules |

---

## 2. Locked Architecture Decisions

These decisions were locked during brainstorming and CANNOT be changed without explicit user approval:

### Decision 1: 1 Global Ticker-Agnostic LSTM + 4 Asset-Aware TFTs per Universe

For each Universe U:
- **LSTM_U**: Ticker-agnostic global model. Sees all tickers as undifferentiated. No ticker embedding. Input: [batch, 252, 31]. Output: 4 continuous returns.
- **TFT_Quad_Array_U**: 4 distinct TFTs (one per horizon: T+1, T+5, T+10, T+15). Ticker_id is a static covariate. QuantileLoss → distribution outputs.
- **5 model artifacts per universe**. For 3 v1 universes (S&P 500, Russell 1000, Russell 2000): **15 models total.**

### Decision 2: 31-Dimensional Feature Contract

Every ticker, every trading day, produces exactly 31 columns:
- **5 raw**: open, high, low, close, volume
- **19 technical**: returns_{1d,5d,10d,20d}, rsi_14, macd, macd_signal, macd_hist, bb_{upper,middle,lower}, bb_width, atr_14, volatility_20d, volume_z_score, sma_{50,200}, price_to_sma{50,200}
- **7 macro**: fed_funds_rate, cpi, unemployment, gdp, yield_spread_10y_2y, vix, high_yield_spread

Locked in `features/feature_engineering/shared/feature_schema.py`. Any change requires a documented architectural deviation.

### Decision 3: Walk-Forward 3-Way Split (70/15/15)

Within each rolling 2-year training window:
- **Train**: First 70% chronologically
- **Calibration**: Next 15% (conformal non-conformity scores; never seen during weight updates)
- **Validation**: Last 15% (early-stopping signal + held-out metrics)

**Random shuffling is FORBIDDEN.** Weekly retraining slides window forward by 7 trading days.

### Decision 4: Locally-Weighted Split Conformal Calibration (NOT Isotonic Regression)

Custom lightweight implementation in `conformal/calibrator.py` (~120 lines of NumPy). Steps:
1. Fit blended model on 70% train slice
2. Generate predictions on 15% calibration slice
3. Compute non-conformity scores, locally weighted by predicted residual magnitude
4. Take (1−α) quantile of scores per horizon (default α=0.10, 90% coverage)
5. Store quantile; at inference: interval = [y_pred − q·r_hat, y_pred + q·r_hat]

### Decision 5: Uncertainty-Aware Ensemble Blending (NOT 60/40 Static)

```python
tft_spread = tft_q90 - tft_q10
spread_z = normalize_against_history(tft_spread)
lstm_w = clip(base_lstm_w + 0.10 * spread_z, 0.40, 0.80)
tft_w = 1.0 - lstm_w
blended = (lstm_pred * lstm_w) + (tft_q50 * tft_w)
```

When TFT is more uncertain (wider spread), lean on LSTM. `base_lstm_w` is config-tunable.

### Decision 6: Continuous Regression Targets (NOT Binary Labels)

Targets are continuous percentage returns:
```python
y_T1 = (close.shift(-1) - close) / close
y_T5 = (close.shift(-5) - close) / close
y_T10 = (close.shift(-10) - close) / close
y_T15 = (close.shift(-15) - close) / close
```
Last 15 rows dropped (future hasn't happened yet).

### Decision 7: HuberLoss for LSTM (NOT BCELoss)

Original spec had `nn.BCELoss` — mathematically incoherent with continuous regression targets. **`nn.HuberLoss`** (smooth L1) is robust to fat-tailed returns. TFT uses `QuantileLoss` (unchanged).

### Decision 8: Conviction Score — Risk-Adjusted Magnitude

```python
sigma = (tft_q90 - tft_q10) / 2.563  # 10-90 spread to ~1σ
z = y_pred / (sigma + 1e-9)
score = clip(z * 25 + 50, 0, 100)
```
Centered at 50 (neutral). Strong bullish ≈ 80+, mild bullish ≈ 55, bearish ≈ 30.

### Decision 9: Long-Only Filter for v1

Conviction tickets only emitted for predicted_return > 0. `SHORT` direction enum reserved in schema for v2.

### Decision 10: Filter Gate Criteria (for Conviction Tickets)

| Criterion | Threshold |
|---|---|
| conviction_score | > 67 |
| predicted_return | > 0 (long-only) |
| backtest_pass_count | ≥ 2 of 4 strategies |
| conformal interval width | < W_max (90th percentile of calibration widths) |

### Decision 11: LSTM Architecture

```python
Bi-LSTM(input_size=31, hidden_size=128, num_layers=3, bidirectional=True)
→ MultiheadAttention(embed_dim=256, num_heads=8)
→ Linear(256,64) → ReLU → Dropout(0.3) → Linear(64,4)
# NO Sigmoid. Output: unbounded ℝ⁴
```

### Decision 12: Training Hyperparameters

| Param | Value |
|---|---|
| Optimizer | AdamW(lr=1e-3, weight_decay=1e-4) |
| LR scheduler | ReduceLROnPlateau(mode='min', patience=5, factor=0.5) |
| Early stopping | 10 consecutive epochs, no val-loss improvement |
| Max epochs | 100 |
| Batch size | 256 (LSTM); pytorch-forecasting chooses for TFT |

---

## 3. Twelve Spec Deviations

These are documented departures from the source PDF, all explicitly approved during brainstorming:

| # | Spec Says | We're Doing | Reason |
|---|---|---|---|
| 1 | LSTM Sigmoid() + BCELoss | Linear() + HuberLoss | BCE expects {0,1}; continuous regression needs Huber |
| 2 | TFT Sigmoid on outputs | Full quantile distributions (q10, q50, q90) | Sigmoid on ~0.02 return ≈ 0.505, contributes nothing |
| 3 | 60/40 LSTM/TFT blend | Uncertainty-aware weighting [0.40, 0.80] | Static weights ignore model's own uncertainty signal |
| 4 | IsotonicRegression calibrator | Locally-weighted split conformal | Isotonic calibrates binary probabilities; doesn't apply to regression |
| 5 | 80/20 train/val split | 70/15/15 train/calibration/validation | Conformal needs distinct calibration set |
| 6 | Filter: P(move) > 0.67 | conviction_score > 67 + backtest + conformal width | P(move) doesn't exist in regression framework |
| 7 | Conviction score undefined | clip(y_pred/sigma * 25 + 50, 0, 100) | Must derive from continuous regression outputs |
| 8 | 4 isotonic models stored | 4 conformal quantiles + 1 residual predictor MLP | Consequence of deviation #4 |
| 9 | LSTM input_size=31 strictly | Same — ticker-agnostic global model (no ticker embedding) | Ticker-aware behavior delegated to TFT |
| 10 | Polygon + Alpha Vantage in failover | yfinance + Alpaca + Stooq (all free) | User scoping; interfaces preserved for later |
| 11 | Backtest: Sharpe > 1.5 only | Sharpe > 1.5 AND total_trades >= 10 AND max_drawdown > -0.40 | Avoid spurious tiny-N passes and exclude blow-ups |
| 12 | Rule 1 says no "alterations" | Deviation #1 is an explicit, documented, approved change | Rule 1 forbids silent alterations; this one is explicit |

---

## 4. Backend Tech Stack & Conventions

### Core Stack

| Layer | Technology | Version |
|---|---|---|
| Runtime | Python | 3.11+ |
| Framework | FastAPI | 0.115.x |
| ORM | SQLAlchemy 2.0 async | 2.0.x |
| DB Driver | asyncpg | 0.30.x |
| Database | PostgreSQL 16 + TimescaleDB | 2.16.x |
| Migrations | Alembic | 1.13.x |
| Package mgmt | uv | latest |
| ML Framework | PyTorch | 2.2.x |
| Training | pytorch-lightning | 2.1.x+ |
| TFT | pytorch-forecasting | 1.0.x+ |
| Indicators | TA-Lib (primary), pandas-ta (fallback) | 0.4.28+ / 0.3.14+ |
| Backtesting | vectorbt | 0.25.x |
| Statistics | scipy | 1.11.x+ |
| Retry | tenacity | 8.2.x+ |
| Logging | loguru | 0.7.x+ |
| Auth | python-jose[cryptography] + argon2-cffi | latest |
| Rate limiting | slowapi | latest |
| CLI | typer | 0.12.x+ |
| Orchestration | Prefect 3 | 3.x |
| Testing | pytest + pytest-asyncio + testcontainers | latest |
| Lint/Format | ruff | latest |

### Feature Layout Convention

Every feature directory follows this structure:
```
features/<name>/
├── models.py          # SQLAlchemy models
├── schemas.py         # Pydantic v2 schemas
├── repository.py      # Data access layer (no raw SQL above this)
├── service.py         # Business logic
├── dependencies.py    # FastAPI dependencies (if needed)
├── router.py          # Router assembly
├── endpoints/         # Individual endpoint handlers
│   ├── list.py
│   ├── detail.py
│   ├── create.py
│   └── ...
├── tests/             # Feature-local tests
│   ├── test_<feature>_service.py
│   └── test_<feature>_endpoints.py
└── features.md        # Feature documentation
```

Sub-features nest the same pattern (e.g., `ml_models/lstm/`, `ml_models/tft/`, `ml_models/ensemble/`, `ml_models/conformal/`).

### Pydantic v2 Patterns

```python
from pydantic import BaseModel, ConfigDict

class UniverseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # NOT orm_mode = True
    id: UUID
    name: str
    display_name: str
    ticker_count: int
```

### Alembic Conventions

- Migrations live in `backend/alembic/`
- `env.py` imports ALL feature models for autogen detection
- Uses **sync engine** (convert async URL to `postgresql+psycopg://...` in env.py)
- First migration: `CREATE EXTENSION IF NOT EXISTS timescaledb;`
- Hypertable calls (`create_hypertable()`) are **hand-added** to migrations — autogen doesn't detect them
- Statement timeout on app connections: 30s

### Error Envelope

All API errors use this structure:
```json
{
  "error_code": "MACHINE_READABLE_CODE",
  "message": "Human-friendly message",
  "details": { "field": "value" },
  "request_id": "req_abc..."
}
```

Codes: `UNIVERSE_NOT_FOUND`, `TICKER_NOT_FOUND`, `INSUFFICIENT_DATA`, `MODEL_NOT_TRAINED`, `BACKTEST_FAILED`, `CONFORMAL_NOT_FIT`, etc.

---

## 5. Data Sources & Failover

### OHLCV Failover Chain

| Priority | Source | Library | Rate Limits |
|---|---|---|---|
| Primary | Yahoo Finance | `yfinance>=0.2.50` | ~2000/hr/IP, unofficial |
| Secondary | Alpaca Market Data | `alpaca-py>=0.30` | Free with paper account |
| Last resort | Stooq | `httpx` (CSV download) | None formally |

### Macro Data

| FRED Series ID | Column Name | Description |
|---|---|---|
| DFF | fed_funds_rate | Federal Funds Effective Rate |
| CPIAUCSL | cpi | Consumer Price Index |
| UNRATE | unemployment | Unemployment Rate |
| GDP | gdp | Gross Domestic Product |
| T10Y2Y | yield_spread_10y_2y | 10Y minus 2Y Treasury Yield |
| VIXCLS | vix | CBOE Volatility Index |
| BAMLH0A0HYM2 | high_yield_spread | High-Yield Master II OAS |

### Retry Configuration

```python
@retry(wait=wait_exponential(multiplier=1, min=2, max=30), stop=stop_after_attempt(3))
```

Per-ticker isolation: if AAPL fails 3 times, MSFT still proceeds. Failed tickers logged in `IngestRun.failed_tickers`.

### Data Cleaning Rules (Non-Negotiable)

- **Timezone stripping**: `df.index = df.index.tz_localize(None)` on every OHLCV frame. TimescaleDB merges break if tz-aware and tz-naive mix.
- **NaN policy**: Raw OHLCV — no NaNs. Macro — forward-fill. Leading NaNs → drop rows.
- **Schema enforcement**: Assert dtypes (float64 for prices, int64 for volume). Mismatches log + coerce.

---

## 6. Data Model Summary

### Tables by Owning Feature

| Table | Feature | Key Notes |
|---|---|---|
| users | auth | Single admin v1; multi-user-ready |
| sessions | auth | Refresh-token-backed |
| universes | universes | Named baskets, system-managed flag |
| tickers | universes | Canonical symbol registry |
| universe_memberships | universes | Time-aware join (added_at, removed_at) |
| ohlcv_bars | data_ingestion | TimescaleDB hypertable on bar_date |
| macro_observations | data_ingestion | TimescaleDB hypertable on observed_date |
| ingest_runs | data_ingestion | Audit + alerting |
| feature_matrix | feature_engineering | TimescaleDB hypertable, 31 cols + 4 targets |
| normalization_stats | feature_engineering | Rolling Z-score parameters |
| training_runs | ml_models | Per-universe, per-week typically |
| model_artifacts | ml_models | 5 active per universe |
| inference_runs | ml_models | Daily |
| predictions | ml_models | Per (ticker, universe, inference_date) |
| backtest_runs | backtesting | Per-universe, weekly |
| backtest_metrics | backtesting | Per (run, ticker, strategy) |
| filter_runs | conviction_tickets | Per inference |
| conviction_tickets | conviction_tickets | The headline output |
| coverage_metrics | monitoring | Conformal coverage tracking |
| feature_drift_metrics | monitoring | Per-feature KL divergence |
| system_alerts | monitoring | Cross-feature alerting |

### Key Indexes

- `(universe_id, removed_at)` on universe_memberships — "active members" queries
- `(ticker_id)` on universe_memberships — "which universes is this ticker in"
- `(ticker_id, bar_date DESC)` on ohlcv_bars — latest-N queries
- `(series_name, observed_date)` on macro_observations — PK
- `(triggered_at DESC)` on ingest_runs — "latest runs"
- `(universe_id, started_at DESC)` on training_runs
- `(universe_id, model_role) WHERE is_active = true` on model_artifacts — partial unique
- `(universe_id, inference_date DESC)` on predictions
- `(ticker_id, inference_date DESC)` on predictions
- `(universe_id, status, conviction_score DESC)` on conviction_tickets — inbox queries
- `(resolution_date, status)` on conviction_tickets — outcome-resolution sweep

---

## 7. Feature-by-Feature Implementation Notes

### Feature 1: Auth & User Accounts

- Single hardcoded admin user, created via `scripts/seed_admin.py`
- JWT access tokens (HS256, 24h) + Postgres-backed hashed refresh tokens (30d sliding)
- Refresh tokens in `sessions` table (boilerplate's session store repurposed)
- `argon2-cffi` for password hashing
- `slowapi` rate limiting: 10/min per IP on login
- Manual password reset: `scripts/reset_password.py` (typer CLI)
- Frontend: JWT in Zustand memory slice; refresh in `HttpOnly Secure SameSite=Strict` cookie
- Endpoints: POST /login, POST /logout, POST /refresh, POST /change-password, GET /sessions, POST /logout-everywhere, GET /me

### Feature 2: Universe Management

- Universe = named, versioned basket of tickers
- Time-aware membership: `added_at` + `removed_at NULL` = active. Removal preserves history.
- Point-in-time snapshots: `?at=<date>` returns members where `added_at <= date AND (removed_at IS NULL OR removed_at > date)`
- Lazy ticker sync: tickers enter registry only when referenced by a universe add (validated against Alpaca)
- `ConstituentSource` Protocol: swappable adapter per index (Wikipedia for S&P 500, iShares CSVs for Russells)
- 3 system-managed universes: S&P 500, Russell 1000, Russell 2000
- Bulk add + CSV import + per-ticker remove
- System-managed universes cannot be deleted or renamed by users

### Feature 3: Data Ingestion (Block A1)

- Failover chain: yfinance (primary) → Alpaca (secondary) → Stooq (last resort)
- `DataFetcher` ABC in `features/data_ingestion/shared/fetcher_base.py`
- FRED macro: 7 series, forward-filled to trading calendar
- Cold-start backfill: 2 years daily OHLCV, 50 tickers/batch
- Daily incremental: after market close, new day's bar
- Gap fill: daily flow detects missing dates, targeted refetch
- Trigger modes: cold_start, daily_scheduled, on_demand, gap_fill
- Output: OHLCVBar + MacroObservation rows + IngestRun audit row

### Feature 4: Feature Engineering (Blocks A2 + A3)

- 31-dimensional contract locked in `feature_schema.py`
- Sub-components: EquityFeatureEngineer, MacroMerger, TargetGenerator, FeatureScaler, TimeSeriesDataset
- Vectorized only — no for loops over rows. TA-Lib primary, pandas-ta fallback.
- Burn-in period: ~200 rows dropped per ticker after calculations
- Lookahead-bias protections: trailing-window only, targets isolated from features, per-ticker scaling
- Rolling 252-day Z-score normalization (never on targets)
- Targets: continuous percentage returns for T+1, T+5, T+10, T+15
- Tensor shape: X=[batch, 252, 31], y=[batch, 4]
- Feature matrix materialized in TimescaleDB (not computed on-the-fly)

### Feature 5: ML Models (Blocks A4 + A5 + A6)

- 1 LSTM per universe (Bi-LSTM 3×128 + 8-head attention + linear head)
- 4 TFTs per universe (one per horizon, QuantileLoss, ticker as static covariate)
- Ensemble: RegimeBlender (uncertainty-aware) + ConformalCalibrator (locally-weighted split conformal)
- Walk-forward 3-way split: 70% train, 15% calibration, 15% validation
- Training: AdamW, ReduceLROnPlateau, early stopping after 10 epochs, max 100
- Conformal: custom NumPy impl (~120 lines), residual predictor MLP, 90% target coverage
- Conviction score: clip(y_pred/sigma * 25 + 50, 0, 100) where sigma = (q90-q10)/2.563
- Model artifact storage: local FS at `~/.mbi/artifacts/` for v1, MinIO-ready swap point
- Active artifact: only one per (universe, model_role). Old artifacts kept for 6 months.

### Feature 6: Backtesting (Block A7)

- 4 strategies: MeanReversion, MomentumCross, VolatilityBreakout, StatArb
- Each inherits from `BaseStrategy` ABC with `generate_signals(df)` → (entries, exits)
- `vectorbt.Portfolio.from_signals()` for execution
- 6 metrics: sharpe_ratio, max_drawdown, total_return, win_rate, profit_factor, total_trades
- Filter pass criteria: sharpe > 1.5 AND total_trades >= 10 AND max_drawdown > -0.40
- Ticker is filter-eligible if it passes ≥ 2 of 4 strategies
- 5-year rolling window default

### Feature 7: Conviction Tickets (Block A8 + Scoring)

- Filter gate: conviction_score > 67 AND predicted_return > 0 AND backtest_passes >= 2 AND conformal_width < W_max
- Up to 4 tickets per ticker (one per horizon)
- Lifecycle: TRADABLE → EXPIRED/REVIEWED → ACTIONED → RESOLVED
- Daily Prefect flow resolves tickets whose horizon ended
- CSV export capped at 10K rows
- Inbox sorted by conviction desc, filterable by universe/horizon/score/backtest/conformal-width

### Feature 8: Monitoring & Model Health

- 7 tracked signals: conformal coverage, train/val loss, conviction-vs-outcome correlation, backtest pass-rate drift, pipeline run success rate, data freshness, feature drift (KL divergence)
- Per-universe model card: last training run, active artifacts, validation metrics, coverage history
- Coverage alert: sustained drop below 80% → critical alert
- Conviction-outcome correlation: Spearman > 0.2 sustained
- Data freshness: alert if > 36 hours since last successful ingest
- Alert routing: loguru + system_alerts table (Slack/email deferred)

### Feature 9: Orchestration (Prefect Flows)

- 7 flows on cron schedules:
  1. `daily_data_refresh` — weekdays 4:20pm ET
  2. `daily_inference` — weekdays 5:30pm ET
  3. `weekly_retrain` — Sundays 6am ET
  4. `weekly_backtest` — Sundays 4am ET
  5. `conformal_coverage_check` — daily 11pm ET
  6. `outcome_resolution` — weekdays 5:00pm ET
  7. `artifact_retention` — weekly Sundays 11pm ET
- Each flow is a thin Prefect layer calling feature services. No business logic in flows.
- Per-task retry: 3 attempts, exponential backoff
- On-failure hook: writes `system_alerts` row
- New artifacts only become `is_active=true` after entire pipeline succeeds

---

## 8. Compatibility Notes (from tech-stack-analysis §5)

Agents MUST be aware of these real friction points:

1. **SQLAlchemy 2.0 async + Alembic**: Alembic doesn't run async migrations natively. Use sync engine in `env.py`, async at runtime.
2. **TimescaleDB + Alembic autogen**: Autogenerate doesn't detect hypertables. Hand-add `create_hypertable()` calls after autogen.
3. **PyTorch + Apple Silicon (MPS)**: MPS works for LSTM but TFT may have rough edges. Document CPU fallback.
4. **yfinance reliability**: Unofficial, breaks for days. Mitigations: tenacity retries, Alpaca+Stooq fallback, `IngestRun.status='partial'`.
5. **Prefect 3 + FastAPI in same Postgres**: Use separate schemas (`prefect` vs `public`). Otherwise migrations fight.
6. **vectorbt + Python version**: Best on Python 3.10–3.11. Pin to 3.11.
7. **pytorch-forecasting + pytorch-lightning**: Tight version coupling. Pin together.
8. **TanStack Query + tab visibility**: TQ pauses polling when tab hidden. Set `refetchIntervalInBackground: true` for training pages.
9. **Pydantic v2 + SQLAlchemy 2.0**: Use `ConfigDict(from_attributes=True)`. NOT `orm_mode = True`.
10. **TimescaleDB hypertable + ON CONFLICT**: Hypertables fully support upserts. Use for incremental ingests.
11. **Loguru + uvicorn logging**: Intercept uvicorn's logger and route through loguru in `core/observability/logging.py`.
12. **Postgres NUMERIC precision**: `NUMERIC(18,8)` for prices/percentages. Don't accidentally cast to float — loses precision.
13. **Statement timeout**: Set `statement_timeout = '30s'` on application connections. Long queries go in Prefect tasks.
14. **Memory for full-universe training**: ~2 GB RAM for feature tensors. Manageable on 8–24 GB VRAM GPUs.
15. **MPS + pytorch_forecasting TFT**: Falls back to CPU. CUDA strongly preferred.

---

## 9. Development Stages Reference

| Stage | Scope | Tasks | Status |
|---|---|---|---|
| S0 | Foundations (walking skeleton) | 9 tasks, 41 sub-tasks | Ready for execution |
| S1 | Auth & Universes (full build) | 8 tasks, 34 sub-tasks | Ready for execution |
| S2 | Data Ingestion (Block A1) | Forthcoming | — |
| S3 | Feature Engineering (Blocks A2+A3) | Forthcoming | — |
| S4 | ML Models (Blocks A4+A5+A6) | Forthcoming | — |
| S5 | Backtesting + Conviction Tickets (Blocks A7+A8) | Forthcoming | — |
| S6 | Monitoring + Orchestration | Forthcoming | — |

---

## 10. Testing Conventions

- **TDD mandatory**: Write tests FIRST. RED → GREEN → REFACTOR.
- **Per-test-database isolation**: testcontainers with `timescale/timescaledb-ha:pg16-latest` image. Each test session gets its own container, migrated to head.
- **Backend**: pytest + pytest-asyncio
- **Feature-local tests**: `features/<name>/tests/test_<feature>_{service,endpoints}.py`
- **Integration tests**: `backend/tests/integration/`
- **E2E**: Playwright in `e2e/` — critical path only
- **Mock external APIs**: Alpaca, yfinance, FRED — all mocked in CI. No live network calls.
- **Test isolation**: Function-scoped transaction rollback within session-scoped testcontainer DB.

---

## 11. Security Conventions

- No secrets in logs (passwords, JWTs, API keys — NEVER logged)
- JWT stored in memory only (Zustand auth slice), not localStorage
- Refresh token in `HttpOnly Secure SameSite=Strict` cookie
- `argon2-cffi` for password hashing (NOT bcrypt)
- Rate limiting: `slowapi` per-IP on login (10/min)
- CORS: explicit frontend origin (NO wildcard)
- `cryptography.Fernet` for encrypting secrets at rest (Alpaca API keys, etc.)
- Manual password reset only (no email infra v1) — `scripts/reset_password.py`
```

---

## 7. Deliverable 5 — Frontend-Agent-Instructions.md

### File Location

`agent-instructions/Frontend-Agent-Instructions.md`

### Full File Content

```markdown
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
│   ├── api-client.ts          # Central fetch wrapper
│   ├── query-client.ts        # TanStack Query client config
│   ├── auth-context.tsx       # Auth provider + route guard
│   └── types/
│       └── api.ts             # Auto-generated from OpenAPI
├── features/
│   ├── auth/
│   │   ├── pages/
│   │   │   ├── LoginPage.tsx
│   │   │   └── AccountSettingsPage.tsx
│   │   ├── api/
│   │   │   ├── useLogin.ts           # TanStack mutation
│   │   │   ├── useSessions.ts        # TanStack query
│   │   │   └── useChangePassword.ts  # TanStack mutation
│   │   ├── components/
│   │   ├── store.ts                  # Zustand auth slice
│   │   └── LoginPage.test.tsx        # Colocated test
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
    ├── components/             # shadcn/ui primitives (Button, Dialog, Table, etc.)
    ├── hooks/                  # Shared custom hooks
    └── utils/                  # Shared utilities
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
    mutationFn: (ticketId: string) => apiClient.patch(`/api/v1/tickets/${ticketId}`, { status: "REVIEWED" }),
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
make gen-api   # Runs: openapi-typescript http://localhost:8000/openapi.json -o src/core/types/api.ts
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
```

---

## 8. Complete File Manifest

| # | File Path | Action | Deliverable | Priority |
|---|---|---|---|---|
| 1 | `opencode.json` | Create (superpowers plugin + graphify MCP) | D1+D2 | High |
| 2 | `.claude-plugin/` | Create (superpowers for Claude Code) | D1 | High |
| 3 | `.cursor-plugin/` | Create (superpowers for Cursor) | D1 | High |
| 4 | `.codex-plugin/` | Create (superpowers for Codex) | D1 | High |
| 5 | `graphify-out/` | Generate (via `graphify .`) | D2 | High |
| 6 | `.claude/skills/graphify/SKILL.md` | Generate (via `graphify install --project`) | D2 | High |
| 7 | `.agents/skills/graphify/SKILL.md` | Generate (via `graphify install --project --platform codex`) | D2 | High |
| 8 | `.cursor/rules/` | Generate (via `graphify install --project --platform cursor`) | D2 | High |
| 9 | `.git/hooks/post-commit` | Generate (via `graphify hook install`) | D2 | High |
| 10 | `.git/hooks/post-checkout` | Generate (via `graphify hook install`) | D2 | High |
| 11 | `.mcp.json` | Create (graphify MCP for Claude Code) | D2 | High |
| 12 | `.cursor/mcp.json` | Create (graphify MCP for Cursor) | D2 | High |
| 13 | `.gitignore` | Create | D2 | High |
| 14 | `AGENTS.md` | Create (top-level agent instructions) | D3 | High |
| 15 | `CLAUDE.md` | Create (Claude Code instructions) | D3 | High |
| 16 | `.cursorrules` | Create (Cursor instructions) | D3 | High |
| 17 | `codex-instructions.md` | Create (Codex instructions) | D3 | Medium |
| 18 | `agent-instructions/` | Create directory | D4 | High |
| 19 | `agent-instructions/Pipeline-A-Agent-Instructions.md` | Create (full content provided) | D4 | High |
| 20 | `agent-instructions/Frontend-Agent-Instructions.md` | Create (full content provided) | D5 | High |

---

## 9. Execution Order

### Phase 1: Tooling Installation (D1 + D2)

These must run first because they install infrastructure that other deliverables reference.

1. **D2.1**: Install graphify CLI (`uv tool install graphifyy`)
2. **D2.2**: Run initial graph build (`graphify . --update`)
3. **D2.3**: Install graphify for all agents (`graphify install --project --platform <platform>`)
4. **D2.4**: Install git hooks (`graphify hook install`)
5. **D2.5–D2.8**: Configure graphify MCP for each agent
6. **D2.9**: Create `.gitignore`
7. **D2.10**: Verify graphify works
8. **D1.1**: Install superpowers for OpenCode (update `opencode.json`)
9. **D1.2**: Install superpowers for Claude Code
10. **D1.3**: Install superpowers for Cursor
11. **D1.4**: Install superpowers for Codex
12. **D1.5**: Verify superpowers loads

### Phase 2: Instruction Files (D4 + D5 + D3)

Write content-heavy files first (they're referenced by D3).

13. **D4**: Create `agent-instructions/` directory
14. **D4**: Create `agent-instructions/Pipeline-A-Agent-Instructions.md` (full content in §6 above)
15. **D5**: Create `agent-instructions/Frontend-Agent-Instructions.md` (full content in §7 above)
16. **D3**: Create `AGENTS.md` (full content in §5 above)
17. **D3**: Create `CLAUDE.md` (full content in §5 above)
18. **D3**: Create `.cursorrules` (full content in §5 above)
19. **D3**: Create `codex-instructions.md` (copy AGENTS.md content)

### Phase 3: Verification

20. Run verification checklist (§10 below)
21. Git init (if not already) + initial commit

---

## 10. Verification Checklist

After all deliverables are complete, verify:

### D1 — Superpowers

- [ ] `opencode.json` exists with superpowers plugin config
- [ ] `.claude-plugin/` directory exists (or superpowers installed via Claude Code command)
- [ ] `.cursor-plugin/` directory exists (or superpowers installed via Cursor command)
- [ ] `.codex-plugin/` directory exists (or superpowers installed via Codex command)
- [ ] Superpowers `using-superpowers` skill auto-triggers in at least one agent

### D2 — Graphify

- [ ] `graphify --help` runs successfully
- [ ] `graphify-out/graph.json` exists and is non-empty
- [ ] `graphify-out/graph.html` exists and is viewable in browser
- [ ] `graphify hook status` shows post-commit and post-checkout hooks installed
- [ ] `graphify query "Pipeline A"` returns relevant results
- [ ] MCP server config present in `opencode.json`, `.mcp.json`, `.cursor/mcp.json`
- [ ] `python -m graphify.serve graphify-out/graph.json` starts without error
- [ ] `.gitignore` exists and excludes `graphify-out/` sub-items (except `graph.json`)

### D3 — Top-Level Instruction Files

- [ ] `AGENTS.md` exists at repo root with all 7 sections
- [ ] `CLAUDE.md` exists at repo root with all 7 sections
- [ ] `.cursorrules` exists at repo root with all sections
- [ ] `codex-instructions.md` exists at repo root
- [ ] All 4 files reference `agent-instructions/Pipeline-A-Agent-Instructions.md`
- [ ] All 4 files reference `agent-instructions/Frontend-Agent-Instructions.md`
- [ ] All 4 files have placeholder comments for future Pipeline B/C references

### D4 — Pipeline-A-Agent-Instructions.md

- [ ] `agent-instructions/Pipeline-A-Agent-Instructions.md` exists
- [ ] Contains all 11 sections (overview, locked decisions, spec deviations, tech stack, data sources, data model, feature-by-feature notes, compatibility notes, dev stages, testing, security)
- [ ] All 12 spec deviations documented
- [ ] All 15 compatibility notes reproduced
- [ ] All 20 tables listed with owning features
- [ ] Locked architecture decisions (12) are clearly documented

### D5 — Frontend-Agent-Instructions.md

- [ ] `agent-instructions/Frontend-Agent-Instructions.md` exists
- [ ] Contains all 15 sections (tech stack, TS strict rules, clean code, React conventions, TanStack Query, state management, API client, testing, quality checks, charts, accessibility, performance, shadcn, env vars, future)
- [ ] TypeScript strict rules are comprehensive (no any, no non-null assertions, branded types, discriminated unions)
- [ ] TanStack Query patterns documented with code examples
- [ ] Testing conventions include colocated tests, MSW mocking, Playwright E2E

### Cross-Cutting

- [ ] No file contains hardcoded secrets
- [ ] All markdown files have consistent formatting
- [ ] All cross-references between files use correct relative paths
- [ ] `git status` shows only expected untracked files

---

## 11. Reference Documents

All reference documents are in the repo root:

| Document | Path | What It Contains |
|---|---|---|
| Pipeline A Design | `mbi-pipeline-a-v1-design.md` | 9 features, tech stack, data model, 12 spec deviations, repo architecture |
| Tech Stack Analysis | `tech-stack-analysis.md` | 59 components, 10 gaps, 20 assumptions, 15 compat notes |
| S0 Dev Plan | `features-to-develop/development-plan-S0.md` | Foundations (9 tasks, 41 sub-tasks) |
| S1 Dev Plan | `features-to-develop/development-plan-S1.md` | Auth & Universes (8 tasks, 34 sub-tasks) |

### External References

| Resource | URL | Purpose |
|---|---|---|
| Obra Superpowers | https://github.com/obra/superpowers | Agentic skills framework |
| Graphify | https://github.com/safishamsi/graphify | Knowledge graph builder |
| Graphify PyPI | `graphifyy` (double-y) | CLI installation package |
| FastAPI Boilerplate | https://github.com/SIDDHESHCHAUDHARI2K24/fastapi_backend_boilerplate | Backend scaffolding base |
| OpenCode Docs | https://opencode.ai | OpenCode configuration reference |

---

*End of handoff document. A new coding session should be able to execute all 5 deliverables using only this document and the reference documents listed above.*
