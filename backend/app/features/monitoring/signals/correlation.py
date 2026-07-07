import uuid
from datetime import date, timedelta

import numpy as np
from scipy.stats import spearmanr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.conviction_tickets.models import ConvictionTicket
from app.features.monitoring import repository as monitoring_repo
from app.features.monitoring.service import AlertService


async def compute_conviction_correlation(
    session: AsyncSession,
    universe_id: uuid.UUID,
    alert_service: AlertService | None = None,
) -> float | None:
    window_start = date.today() - timedelta(days=90)
    stmt = select(
        ConvictionTicket.conviction_score, ConvictionTicket.actual_return
    ).where(
        ConvictionTicket.universe_id == universe_id,
        ConvictionTicket.resolution_date >= window_start,
        ConvictionTicket.actual_return.isnot(None),
    )
    result = await session.execute(stmt)
    rows = result.all()

    if len(rows) < 20:
        return None

    scores = np.array([float(r[0]) for r in rows], dtype=np.float64)
    returns = np.array([float(r[1]) for r in rows], dtype=np.float64)

    corr_result = spearmanr(scores, returns)
    corr = float(corr_result.correlation)

    if alert_service is not None and corr < 0.2:
        existing = await monitoring_repo.find_open_alert(
            session, "CONVICTION_UNPREDICTIVE", universe_id
        )
        sustained_count = (
            (existing.context.get("sustained_count", 0) + 1) if existing else 1
        )
        context = {
            "correlation": corr,
            "sustained_count": sustained_count,
            "sample_size": len(rows),
        }

        if sustained_count >= 3:
            await alert_service.raise_alert(
                session,
                severity="warning",
                code="CONVICTION_UNPREDICTIVE",
                message=f"Conviction-return Spearman correlation {corr:.4f} sustained below 0.2 for {sustained_count} measurements",
                universe_id=universe_id,
                context=context,
            )
        elif existing:
            await monitoring_repo.update_alert_context(session, existing.id, context)
        else:
            await monitoring_repo.create_alert(
                session,
                severity="info",
                code="CONVICTION_UNPREDICTIVE",
                message=f"Conviction correlation {corr:.4f} < 0.2 (measurement {sustained_count}/3)",
                universe_id=universe_id,
                context=context,
            )

    return corr
