import logging
import uuid

import httpx

logger = logging.getLogger(__name__)


class SlackNotifier:
    def __init__(self, webhook_url: str | None = None) -> None:
        self.webhook_url = webhook_url

    async def send(
        self,
        severity: str,
        code: str,
        message: str,
        universe_id: uuid.UUID | None = None,
    ) -> bool:
        if not self.webhook_url:
            return False

        try:
            payload = {
                "text": (
                    f"*[{severity.upper()}] {code}*\n"
                    f"Universe: {universe_id or 'global'}\n"
                    f"{message}"
                )
            }
            async with httpx.AsyncClient() as client:
                await client.post(self.webhook_url, json=payload, timeout=5.0)
            return True
        except Exception:
            logger.warning(
                "Slack notification failed (severity=%s, code=%s)",
                severity,
                code,
                exc_info=True,
            )
            return False
