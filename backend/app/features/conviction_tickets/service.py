import uuid
from datetime import timedelta

from sqlalchemy import select

from app.features.conviction_tickets import repository
from app.features.conviction_tickets.filter.gate import evaluate_filter
from app.features.conviction_tickets.models import ConvictionTicket
from app.features.data_ingestion.shared.trading_calendar import trading_days

HORIZON_META = {
    0: {"label": "T1", "days": 1},
    1: {"label": "T5", "days": 5},
    2: {"label": "T10", "days": 10},
    3: {"label": "T15", "days": 15},
}

HORIZON_IDX_TO_SESSIONS_IDX = {0: 1, 1: 5, 2: 10, 3: 15}

PRED_COL_KEYS = ["t1", "t5", "t10", "t15"]


class TicketService:
    async def emit_tickets(
        self,
        session,
        inference_run,
        predictions: list,
        backtest_metrics: list[dict],
        w_max: dict[int, float],
        backtest_run_id: uuid.UUID | None = None,
    ):
        pred_dicts = _predictions_to_dicts(predictions)
        backtest_passes = _build_backtest_passes(backtest_metrics)
        backtest_strategies = _build_backtest_strategies(backtest_metrics)

        passing = evaluate_filter(pred_dicts, backtest_passes, w_max)

        if not passing:
            filter_run = await repository.create_filter_run(
                session,
                inference_run.id,
                backtest_run_id=backtest_run_id,
                num_evaluated=len(pred_dicts),
                num_emitted=0,
                config={"w_max": w_max},
            )
            return [], filter_run

        inference_date = inference_run.inference_date
        sessions = trading_days(inference_date, inference_date + timedelta(days=90))

        ticket_dicts: list[dict] = []
        for p in passing:
            horizon_idx = p["horizon_idx"]
            needed_sessions_idx = HORIZON_IDX_TO_SESSIONS_IDX[horizon_idx]
            if needed_sessions_idx < len(sessions):
                resolution_date = sessions[needed_sessions_idx]
            else:
                resolution_date = sessions[-1] if sessions else inference_date

            ticker_id_str = p["ticker_id"]
            strategies = backtest_strategies.get(ticker_id_str, [])

            ticket_dicts.append(
                {
                    "inference_run_id": inference_run.id,
                    "ticker_id": uuid.UUID(ticker_id_str),
                    "universe_id": uuid.UUID(p["universe_id"])
                    if p.get("universe_id")
                    else inference_run.universe_id,
                    "inference_date": inference_date,
                    "horizon": HORIZON_META[horizon_idx]["label"],
                    "direction": "LONG",
                    "predicted_return": p["pred"],
                    "conviction_score": p["conviction"],
                    "conformal_lower": p["pred_lo"],
                    "conformal_upper": p["pred_hi"],
                    "backtest_passes": p["backtest_passes"],
                    "backtest_pass_strategies": strategies,
                    "status": "TRADABLE",
                    "resolution_date": resolution_date,
                }
            )

        filter_run = await repository.create_filter_run(
            session,
            inference_run.id,
            backtest_run_id=backtest_run_id,
            num_evaluated=len(pred_dicts),
            num_emitted=len(ticket_dicts),
            config={"w_max": w_max},
        )

        await repository.upsert_tickets(session, ticket_dicts)

        result = await session.execute(
            select(ConvictionTicket).where(
                ConvictionTicket.inference_run_id == inference_run.id
            )
        )
        tickets = list(result.scalars().all())

        return tickets, filter_run


def _predictions_to_dicts(predictions: list) -> list[dict]:
    result: list[dict] = []
    for p in predictions:
        for horizon_idx, key in enumerate(PRED_COL_KEYS):
            pred_val = getattr(p, f"pred_{key}", 0.0)
            pred_lo = getattr(p, f"pred_lo_{key}", 0.0)
            pred_hi = getattr(p, f"pred_hi_{key}", 0.0)
            conviction = getattr(p, f"conviction_{key}", 0.0)
            result.append(
                {
                    "ticker_id": str(p.ticker_id),
                    "horizon_idx": horizon_idx,
                    "pred": pred_val,
                    "pred_lo": pred_lo,
                    "pred_hi": pred_hi,
                    "conviction": conviction,
                    "width": pred_hi - pred_lo,
                    "universe_id": str(p.universe_id),
                }
            )
    return result


def _build_backtest_passes(backtest_metrics: list[dict]) -> dict[str, int]:
    return {m["ticker_id"]: m["passes"] for m in backtest_metrics}


def _build_backtest_strategies(backtest_metrics: list[dict]) -> dict[str, list[str]]:
    return {
        m["ticker_id"]: [k for k, v in m.get("strategies", {}).items() if v]
        for m in backtest_metrics
    }
