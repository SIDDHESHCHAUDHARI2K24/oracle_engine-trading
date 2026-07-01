"""Backtesting API router."""

from fastapi import APIRouter

from app.features.backtesting.endpoints.backtest import router as backtest_router

router = APIRouter(prefix="/api/v1/backtests", tags=["backtesting"])
router.include_router(backtest_router)
