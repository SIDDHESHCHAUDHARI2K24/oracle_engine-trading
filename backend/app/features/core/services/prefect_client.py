"""Prefect monitoring read-model client.

Queries Prefect's API (not the DB directly) for recent flow-run status
to power the ingestion monitoring panel. Decouples us from Prefect's
internal schema.
"""

from typing import Any

from prefect.client.orchestration import get_client


async def get_recent_runs(
    deployment_name: str = "daily-data-refresh",
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return recent flow runs for a deployment via Prefect API.

    Returns:
        List of dicts with: id, name, state, start_time, end_time, tags.
    """
    try:
        async with get_client() as client:
            runs = await client.read_flow_runs(
                limit=limit,
                sort="-created",  # type: ignore[arg-type]
            )
            result = []
            for run in runs:
                if (
                    hasattr(run, "deployment_name")
                    and run.deployment_name != deployment_name
                ):
                    continue
                result.append(
                    {
                        "id": str(run.id),
                        "name": run.name,
                        "state": str(run.state_type) if run.state else "unknown",
                        "start_time": run.start_time.isoformat()
                        if run.start_time
                        else None,
                        "end_time": run.end_time.isoformat() if run.end_time else None,
                    }
                )
            return result
    except Exception:
        return []
