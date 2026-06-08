# Quarterly Index Refresh Runbook

## Overview

Re-run the seed script to reconcile system-managed universe constituents with
current index membership.

## Prerequisites

- Backend environment with `DATABASE_URL` configured
- `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` in `.env`
- Network access to Wikipedia and iShares

## Steps

1. Navigate to backend directory:
   ```bash
   cd backend
   ```

2. Run the seed script:
   ```bash
   uv run python scripts/seed_universes.py
   ```

3. Verify the output:
   - Each index should log: `Fetched N constituents`
   - Added / Already present / Invalid breakdowns
   - Reconciliation preserves membership history

## What Happens

- Fetches latest constituents from Wikipedia (S&P 500) and iShares (Russell 1000/2000)
- Validates all symbols against Alpaca
- Adds new constituents (time-aware membership)
- Marks departed constituents as removed (preserving history)
- Idempotent — safe to run multiple times

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Wikipedia table format changed | Update `backend/app/features/universes/shared/constituents/adapters/sp500.py` |
| iShares CSV format changed | Update `backend/app/features/universes/shared/constituents/adapters/russell1000.py` or `russell2000.py` |
| Alpaca reports symbols invalid | Check symbol normalization (dots→dashes, uppercase) in `shared/alpaca_assets.py` |
| Database connection failed | Verify `DATABASE_URL` in `.env` |
