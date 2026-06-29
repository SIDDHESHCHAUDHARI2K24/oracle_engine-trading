"""Register all MBI data flows as Prefect deployments.

Run once after Prefect server starts to create scheduled deployments.
Re-running updates (doesn't duplicate) existing deployments.

Usage:
    uv run python -m app.orchestration.deployments
"""

import asyncio


from app.orchestration.flows.daily_data_refresh import daily_data_refresh_flow


def deploy_daily_refresh():
    """Deploy the daily data refresh flow with weekday after-close schedule."""
    daily_data_refresh_flow.serve(
        name="daily-data-refresh",
        cron="30 16 * * 1-5",
        timezone="America/New_York",
        description="Daily after-close OHLCV + macro refresh with gap fill",
    )


async def main():
    deploy_daily_refresh()
    print("Deployments registered. Keeping process alive for serve...")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
