# MBI Labs Oracle Engine

Self-improving research-grade ML pipeline for equity market prediction. Ingests OHLCV + macroeconomic data across multiple equity universes, engineers a 31-dimensional feature tensor per ticker per day, trains Bi-LSTM and Temporal Fusion Transformer models per universe, and emits filtered Conviction Tickets for human review.

**Current scope**: Pipeline A — the Deep Learning Math Engine.

---

## Prerequisites

| Tool | Version | Required For |
|------|---------|-------------|
| Python | 3.11+ | Backend runtime |
| Node | 20+ | Frontend runtime |
| uv | latest | Python package management |
| pnpm | latest | Node package management |
| Docker | latest | MinIO dev service, E2E tests |
| PostgreSQL 16 | 16.x | Database |
| TimescaleDB | 2.16.x | Time-series data (hypertables) |

### Installing TimescaleDB

**macOS (Homebrew)**:
```bash
brew install postgresql@16 timescaledb
timescaledb-tune --yes
brew services restart postgresql@16
```

**Ubuntu / Debian**:
```bash
sudo sh -c "echo 'deb https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -c -s) main' > /etc/apt/sources.list.d/timescaledb.list"
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | sudo apt-key add -
sudo apt update
sudo apt install timescaledb-2-postgresql-16
sudo timescaledb-tune --yes
sudo systemctl restart postgresql
```

**Windows (WSL2)**:
Follow the Ubuntu instructions inside WSL2. Native Windows is not supported — TimescaleDB requires the Postgres extension API which is unavailable in the Windows Postgres build.

**Docker fallback** (if native install is not feasible):
```bash
docker run -d --name mbi-postgres \
  -e POSTGRES_USER=mbi_user \
  -e POSTGRES_PASSWORD=mbi_password \
  -e POSTGRES_DB=mbi \
  -p 5433:5432 \
  timescale/timescaledb-ha:pg16
```

---

## One-Time Setup

```bash
# 1. Clone the repo
git clone <repo-url> && cd oracle-engine-trading

# 2. Copy and fill in environment variables
cp .env.example .env
# Edit .env: set JWT_SECRET to a random 64-character string

# 3. Install backend dependencies
cd backend
uv sync

# 4. Install frontend dependencies
cd frontend
pnpm install

# 5. Create the database
createdb -U postgres mbi
psql -U postgres -d mbi -c "CREATE ROLE mbi_user WITH LOGIN PASSWORD 'mbi_password';"
psql -U postgres -d mbi -c "GRANT ALL PRIVILEGES ON DATABASE mbi TO mbi_user;"

# 6. Verify TimescaleDB
make db-check

# 7. Run migrations
make migrate

# 8. Seed the database
cd backend && uv run python scripts/seed_admin.py
cd backend && uv run python scripts/seed_universes.py

# 9. Install pre-commit hooks
pre-commit install
```

---

## Development

```bash
# Start full stack (MinIO + backend + frontend)
make dev

# Backend API:     http://localhost:8000
# Frontend UI:     http://localhost:5173
# API Docs:        http://localhost:8000/docs
# MinIO Console:   http://localhost:9001

# Run all tests
make test

# Lint and format
make lint
make format

# Generate TypeScript types from OpenAPI
make gen-api
```

---

## Project Structure

```
.
├── backend/           FastAPI + SQLAlchemy 2.0 async
│   ├── alembic/       Database migrations
│   ├── scripts/       CLI tools (seed, admin)
│   └── src/backend/   Application code
│       ├── core/      DB, settings, logging
│       └── features/  Auth, Universes, Data, ML, Backtesting, Tickets, Monitoring
├── frontend/          Vite + React 18 + TypeScript strict
│   └── src/
│       ├── core/      API client, auth, types
│       ├── features/  Mirrors backend feature names
│       └── shared/    Components, utils, hooks
├── e2e/              Playwright end-to-end tests
├── docs/             Design documents, architecture specs
├── agent-instructions/  Per-pipeline agent instruction files
└── graphify-out/     Knowledge graph (auto-rebuilt on commit)
```

---

## Documentation

- [Pipeline A Design](docs/mbi-pipeline-a-v1-design.md)
- [Tech Stack Analysis](docs/tech-stack-analysis.md)
- [Development Plan S0](features-to-develop/development-plan-S0.md)
- [Development Plan S1](features-to-develop/development-plan-S1.md)
