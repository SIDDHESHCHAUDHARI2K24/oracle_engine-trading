"""Register all MBI data flows as Prefect deployments.

Run once after Prefect server starts to create scheduled deployments.
Re-running updates (doesn't duplicate) existing deployments.

Usage:
    uv run python -m app.orchestration.deployments
"""

import asyncio


from app.orchestration.flows.conformal_coverage_check import conformal_coverage_check_flow
from app.orchestration.flows.artifact_retention import artifact_retention_flow
from app.orchestration.flows.daily_data_refresh import daily_data_refresh_flow
from app.orchestration.flows.daily_inference import daily_inference_flow
from app.orchestration.flows.daily_monitoring import daily_monitoring_flow
from app.orchestration.flows.outcome_resolution import outcome_resolution_flow
from app.orchestration.flows.weekly_backtest import weekly_backtest_flow
from app.orchestration.flows.weekly_retrain import weekly_retrain_flow


def deploy_daily_refresh():
    """Deploy the daily data refresh flow with weekday after-close schedule."""
    daily_data_refresh_flow.serve(
        name="daily-data-refresh",
        cron="30 16 * * 1-5",
        timezone="America/New_York",
        description="Daily after-close OHLCV + macro refresh with gap fill",
    )


def deploy_daily_inference():
    """Deploy the daily inference flow, weekdays at 5:30pm ET."""
    daily_inference_flow.serve(
        name="daily-inference",
        cron="30 17 * * 1-5",
        timezone="America/New_York",
        description="Daily inference across all active universes post-feature-compute",
    )


def deploy_weekly_backtest():
    """Deploy the weekly backtest flow, Sundays at 4am ET."""
    weekly_backtest_flow.serve(
        name="weekly-backtest",
        cron="0 4 * * 0",
        timezone="America/New_York",
        description="Weekly backtest of all 4 strategies per universe (Sundays 4am ET)",
    )


def deploy_outcome_resolution():
    """Deploy the outcome resolution flow, weekdays at 5pm ET."""
    outcome_resolution_flow.serve(
        name="outcome-resolution",
        cron="0 17 * * 1-5",
        timezone="America/New_York",
        description="Resolve conviction tickets whose horizon ended today",
    )


def deploy_weekly_retrain():
    """Deploy the weekly retrain flow, Sundays at 6am ET."""
    weekly_retrain_flow.serve(
        name="weekly-retrain",
        cron="0 6 * * 0",
        timezone="America/New_York",
        description="Weekly retrain + champion/challenger promotion for all active universes",
    )


def deploy_conformal_coverage_check():
    """Deploy the conformal coverage check flow, daily at 11pm ET."""
    conformal_coverage_check_flow.serve(
        name="conformal-coverage-check",
        cron="0 23 * * *",
        timezone="America/New_York",
        description="Daily conformal coverage check for all active universes (daily 11pm ET)",
    )


def deploy_daily_monitoring():
    """Deploy the daily monitoring flow, daily at 10pm ET."""
    daily_monitoring_flow.serve(
        name="daily-monitoring",
        cron="0 22 * * *",
        timezone="America/New_York",
        description="Daily monitoring signals: freshness, pipeline success, and Mon/Thu heavy signals (daily 10pm ET)",
    )


def deploy_artifact_retention():
    """Deploy the artifact retention reaper, Sundays at 11pm ET."""
    artifact_retention_flow.serve(
        name="artifact-retention",
        cron="0 23 * * 0",
        timezone="America/New_York",
        description="Weekly artifact retention — archives inactive artifacts older than 6 months",
    )


async def main():
    deploy_daily_refresh()
    deploy_daily_inference()
    deploy_outcome_resolution()
    deploy_weekly_backtest()
    deploy_weekly_retrain()
    deploy_conformal_coverage_check()
    deploy_daily_monitoring()
    deploy_artifact_retention()
    print("Deployments registered. Keeping process alive for serve...")
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
