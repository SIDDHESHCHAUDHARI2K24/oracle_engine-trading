import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.notifier import SlackNotifier
from app.features.core.config import get_settings
from app.features.monitoring import repository as monitoring_repo
from app.features.monitoring.models import SystemAlert


class AlertService:
    def __init__(self, notifier: SlackNotifier | None = None) -> None:
        if notifier is not None:
            self._notifier = notifier
        else:
            settings = get_settings()
            url = settings.slack_webhook_url or None
            self._notifier = SlackNotifier(webhook_url=url)

    async def raise_alert(
        self,
        session: AsyncSession,
        severity: str,
        code: str,
        message: str,
        universe_id: uuid.UUID | None = None,
        context: dict | None = None,
    ) -> SystemAlert:
        existing = await monitoring_repo.find_open_alert(session, code, universe_id)
        if existing is not None:
            updated = await monitoring_repo.update_alert_context(
                session, existing.id, context or {}
            )
            return updated  # type: ignore[return-value]

        alert = await monitoring_repo.create_alert(
            session, severity, code, message, universe_id, context
        )

        if severity == "critical":
            await self._notifier.send(
                severity=severity,
                code=code,
                message=message,
                universe_id=universe_id,
            )

        return alert

    async def acknowledge_alert(
        self,
        session: AsyncSession,
        alert_id: uuid.UUID,
    ) -> SystemAlert | None:
        return await monitoring_repo.acknowledge_alert(session, alert_id)

    async def resolve_alert(
        self,
        session: AsyncSession,
        alert_id: uuid.UUID,
    ) -> SystemAlert | None:
        return await monitoring_repo.resolve_alert(session, alert_id)

    async def list_open_alerts(
        self,
        session: AsyncSession,
        severity: str | None = None,
        universe_id: uuid.UUID | None = None,
    ) -> list[SystemAlert]:
        return await monitoring_repo.list_open_alerts(session, severity, universe_id)
