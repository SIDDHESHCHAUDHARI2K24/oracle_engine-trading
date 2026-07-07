import uuid
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.conviction_tickets.models import ConvictionTicket
from app.features.monitoring import repository as monitoring_repo
from app.features.monitoring.service import AlertService

HORIZONS = ["T1", "T5", "T10", "T15"]
WINDOWS = [30, 90]
BREACH_THRESHOLD = 0.80
BREACH_LOOKBACK = 5
MIN_TICKET_COUNT = 5


class CoverageSignal:
    def __init__(self, alert_service: AlertService | None = None) -> None:
        self._alert_service = alert_service or AlertService()

    async def compute(
        self,
        session: AsyncSession,
        universe_id: uuid.UUID,
        measurement_date: date,
    ) -> None:
        for horizon in HORIZONS:
            for window in WINDOWS:
                cutoff = measurement_date - timedelta(days=window)
                tickets = await self._get_resolved_tickets(
                    session, universe_id, horizon, cutoff, measurement_date
                )

                if len(tickets) < MIN_TICKET_COUNT:
                    await monitoring_repo.upsert_coverage_metric(
                        session,
                        universe_id=universe_id,
                        horizon=horizon,
                        measurement_date=measurement_date,
                        window_size=window,
                        realized_coverage=None,
                        num_tickets_resolved=len(tickets),
                    )
                    continue

                covered = 0
                for ticket in tickets:
                    if (
                        ticket.actual_return is not None
                        and ticket.conformal_lower
                        <= ticket.actual_return
                        <= ticket.conformal_upper
                    ):
                        covered += 1

                realized_coverage = covered / len(tickets)
                is_alert = realized_coverage < BREACH_THRESHOLD

                await monitoring_repo.upsert_coverage_metric(
                    session,
                    universe_id=universe_id,
                    horizon=horizon,
                    measurement_date=measurement_date,
                    window_size=window,
                    realized_coverage=realized_coverage,
                    num_tickets_resolved=len(tickets),
                    is_alert=is_alert,
                )

                if is_alert:
                    recent = await monitoring_repo.get_recent_coverages(
                        session,
                        universe_id=universe_id,
                        horizon=horizon,
                        window_size=window,
                        limit=BREACH_LOOKBACK,
                    )
                    if len(recent) >= BREACH_LOOKBACK and all(
                        r.realized_coverage is not None
                        and r.realized_coverage < BREACH_THRESHOLD
                        for r in recent
                    ):
                        await self._alert_service.raise_alert(
                            session,
                            severity="critical",
                            code="COVERAGE_BREACH",
                            message=(
                                f"Sustained coverage breach for {horizon}/{window}d: "
                                f"{realized_coverage:.2%} over {BREACH_LOOKBACK} measurements"
                            ),
                            universe_id=universe_id,
                            context={
                                "horizon": horizon,
                                "window_size": window,
                                "realized_coverage": realized_coverage,
                                "measurement_date": measurement_date.isoformat(),
                                "breach_lookback": BREACH_LOOKBACK,
                            },
                        )

    async def _get_resolved_tickets(
        self,
        session: AsyncSession,
        universe_id: uuid.UUID,
        horizon: str,
        cutoff: date,
        measurement_date: date,
    ) -> list[ConvictionTicket]:
        result = await session.execute(
            select(ConvictionTicket).where(
                ConvictionTicket.universe_id == universe_id,
                ConvictionTicket.horizon == horizon,
                ConvictionTicket.resolution_date >= cutoff,
                ConvictionTicket.resolution_date <= measurement_date,
                ConvictionTicket.status.in_(["TRADABLE", "REVIEWED", "ACTIONED"]),
            )
        )
        return list(result.scalars().all())
