"""Application entrypoint and FastAPI factory.

This module configures the FastAPI app instance, attaches middleware
such as CORS, and wires feature routers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from fastapi import Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.auth.routers import auth_router
from app.features.core.config import settings
from app.features.core.database import get_async_session
from app.features.core.limiter import limiter, rate_limit_exceeded_handler
from app.features.core.observability.logging import configure_logging
from app.features.core.observability.middleware import RequestIdMiddleware
from app.features.data_ingestion.router import router as data_ingestion_router
from app.features.feature_engineering.router import router as feature_engineering_router
from app.features.backtesting.router import router as backtesting_router
from app.features.ml_models.router import router as ml_models_router
from app.features.universes.endpoints.ticker_sync import ticker_sync_router
from app.features.conviction_tickets.router import router as conviction_tickets_router
from app.features.universes.router import universes_router


def create_app() -> FastAPI:
    """Create and configure the main FastAPI application instance."""
    configure_logging()

    app = FastAPI(title=settings.project_name)

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(RequestIdMiddleware)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        """Simple health check endpoint — process alive."""
        return {"status": "ok"}

    @app.get("/ready", tags=["system"])
    async def ready(
        db: AsyncSession = Depends(get_async_session),
    ) -> JSONResponse:
        """Readiness check — DB reachable."""
        try:
            result = await db.execute(text("SELECT 1 AS ok"))
            return JSONResponse(
                status_code=200,
                content={"status": "ok", "db": str(result.scalar_one())},
            )
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "detail": "database unreachable"},
            )

    app.include_router(auth_router)
    app.include_router(universes_router)
    app.include_router(ticker_sync_router)
    app.include_router(data_ingestion_router)
    app.include_router(feature_engineering_router)
    app.include_router(backtesting_router)
    app.include_router(ml_models_router)
    app.include_router(conviction_tickets_router)

    return app
