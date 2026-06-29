"""GET /api/v1/feature_engineering/inspect — view all features for a ticker/date."""

import uuid
from datetime import date as date_type

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.core.database import get_async_session
from app.features.feature_engineering.repository import (
    get_feature_row,
    get_normalization_stats,
)
from app.features.feature_engineering.schemas import FeatureInspectResponse

inspect_router = APIRouter()


@inspect_router.get("/inspect", response_model=FeatureInspectResponse)
async def inspect_features(
    ticker_id: uuid.UUID = Query(..., alias="ticker"),
    date: date_type = Query(..., alias="date"),
    session: AsyncSession = Depends(get_async_session),
) -> FeatureInspectResponse:
    """Return all 31 raw + normalized features, 4 targets, and stats for one cell."""
    row = await get_feature_row(session, ticker_id, date)
    if row is None:
        raise HTTPException(status_code=404, detail="Feature row not found")

    stats = await get_normalization_stats(session, ticker_id, date)

    features = {}
    for col in row.__table__.columns:
        col_name = str(col.name)
        if col_name.startswith("target"):
            continue
        val = getattr(row, col_name, None)
        features[col_name] = float(val) if val is not None else None

    targets = {}
    for target_col in ["target_t1", "target_t5", "target_t10", "target_t15"]:
        val = getattr(row, target_col, None)
        targets[target_col] = float(val) if val is not None else None

    stats_list = [
        {
            "feature_name": s.feature_name,
            "rolling_mean": float(s.rolling_mean),
            "rolling_std": float(s.rolling_std),
        }
        for s in stats
    ]

    return FeatureInspectResponse(
        ticker=str(ticker_id),
        date=date,
        features=features,
        targets=targets,
        stats=stats_list,
    )
