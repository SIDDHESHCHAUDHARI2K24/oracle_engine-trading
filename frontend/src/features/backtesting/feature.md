# Backtesting

## Overview
Post-inference backtest validation results explorer. Shows which strategies passed/failed for each ticker in a universe, with detailed metrics and equity curves.

## API
- `GET /api/v1/backtests/{universe_id}` - Universe pass summary grid
- `GET /api/v1/backtests/{universe_id}/{ticker_id}` - Per-ticker strategy detail with equity curves

## Routes
- `/backtests/:universeId` - Explorer with pass badge grid
- `/backtests/:universeId/:tickerId` - Ticker detail with metrics, equity curves, drawdowns

## Components
- `EquityCurveChart` - lightweight-charts area chart
- `DrawdownChart` - recharts LineChart with red fill

## State
- TanStack Query with `backtestKeys` factory
- Charts cleanup on unmount
