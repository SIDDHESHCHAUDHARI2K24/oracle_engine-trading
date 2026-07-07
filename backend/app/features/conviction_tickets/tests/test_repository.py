import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import text


async def _seed_universe(db_session, universe_id, name):
    await db_session.execute(
        text(
            "INSERT INTO universes (id, name, display_name, created_at) "
            "VALUES (:id, :name, :dn, now())"
        ),
        {"id": universe_id, "name": name, "dn": f"Display {name}"},
    )


async def _seed_ticker(db_session, ticker_id, symbol):
    await db_session.execute(
        text(
            "INSERT INTO tickers (id, symbol, name, created_at, active) "
            "VALUES (:id, :sym, :name, now(), true)"
        ),
        {"id": ticker_id, "sym": symbol, "name": f"Ticker {symbol}"},
    )


async def _seed_inference_run(db_session, inf_run_id, universe_id, dt):
    await db_session.execute(
        text(
            "INSERT INTO inference_runs (id, universe_id, triggered_by, inference_date, status) "
            "VALUES (:id, :uid, :trig, :dt, 'completed')"
        ),
        {"id": inf_run_id, "uid": universe_id, "trig": "test", "dt": dt},
    )


async def _seed_backtest_run(db_session, bt_run_id, universe_id):
    await db_session.execute(
        text(
            "INSERT INTO backtest_runs (id, universe_id, triggered_by, backtest_period_start, backtest_period_end, status, num_strategies, metadata) "
            "VALUES (:id, :uid, :trig, :start, :end, 'completed', 4, '{}'::jsonb)"
        ),
        {
            "id": bt_run_id,
            "uid": universe_id,
            "trig": "test",
            "start": date.today() - timedelta(days=365),
            "end": date.today(),
        },
    )


@pytest.mark.asyncio
class TestTicketRepository:
    async def test_upsert_tickets_inserts_new(self, db_session):
        from app.features.conviction_tickets.repository import upsert_tickets

        ticker_id = uuid.uuid4()
        universe_id = uuid.uuid4()
        inf_run_id = uuid.uuid4()

        await _seed_universe(db_session, universe_id, "test-u1")
        await _seed_ticker(db_session, ticker_id, "TEST")
        await _seed_inference_run(db_session, inf_run_id, universe_id, date.today())
        await db_session.flush()

        ticket_dicts = [
            {
                "inference_run_id": inf_run_id,
                "ticker_id": ticker_id,
                "universe_id": universe_id,
                "inference_date": date.today(),
                "horizon": "T1",
                "direction": "LONG",
                "predicted_return": 0.02,
                "conviction_score": 80.0,
                "conformal_lower": 0.01,
                "conformal_upper": 0.04,
                "backtest_passes": 3,
                "backtest_pass_strategies": ["mac", "ma_cross", "bb"],
                "status": "TRADABLE",
                "resolution_date": date.today(),
            }
        ]

        count = await upsert_tickets(db_session, ticket_dicts)
        assert count == 1

    async def test_upsert_tickets_idempotent(self, db_session):
        from app.features.conviction_tickets.repository import upsert_tickets

        ticker_id = uuid.uuid4()
        universe_id = uuid.uuid4()
        inf_run_id = uuid.uuid4()

        await _seed_universe(db_session, universe_id, "test-u2")
        await _seed_ticker(db_session, ticker_id, "IDEM")
        await _seed_inference_run(db_session, inf_run_id, universe_id, date.today())
        await db_session.flush()

        ticket_dicts = [
            {
                "inference_run_id": inf_run_id,
                "ticker_id": ticker_id,
                "universe_id": universe_id,
                "inference_date": date.today(),
                "horizon": "T5",
                "direction": "LONG",
                "predicted_return": 0.03,
                "conviction_score": 75.0,
                "conformal_lower": 0.02,
                "conformal_upper": 0.05,
                "backtest_passes": 2,
                "backtest_pass_strategies": ["mac", "bb"],
                "status": "TRADABLE",
                "resolution_date": date.today(),
            }
        ]

        count1 = await upsert_tickets(db_session, ticket_dicts)
        assert count1 == 1

        count2 = await upsert_tickets(db_session, ticket_dicts)
        assert count2 == 0

    async def test_get_ticket_by_id(self, db_session):
        from app.features.conviction_tickets.repository import (
            upsert_tickets,
            get_ticket_by_id,
        )
        from app.features.conviction_tickets.models import ConvictionTicket
        from sqlalchemy import select

        ticker_id = uuid.uuid4()
        universe_id = uuid.uuid4()
        inf_run_id = uuid.uuid4()

        await _seed_universe(db_session, universe_id, "test-u3")
        await _seed_ticker(db_session, ticker_id, "FIND")
        await _seed_inference_run(db_session, inf_run_id, universe_id, date.today())
        await db_session.flush()

        ticket_dicts = [
            {
                "inference_run_id": inf_run_id,
                "ticker_id": ticker_id,
                "universe_id": universe_id,
                "inference_date": date.today(),
                "horizon": "T1",
                "direction": "LONG",
                "predicted_return": 0.02,
                "conviction_score": 80.0,
                "conformal_lower": 0.01,
                "conformal_upper": 0.04,
                "backtest_passes": 3,
                "backtest_pass_strategies": ["mac", "ma_cross"],
                "status": "TRADABLE",
                "resolution_date": date.today(),
            }
        ]
        await upsert_tickets(db_session, ticket_dicts)

        result = await db_session.execute(
            select(ConvictionTicket).where(
                ConvictionTicket.inference_run_id == inf_run_id
            )
        )
        created = result.scalar_one()
        tid = created.id

        found = await get_ticket_by_id(db_session, tid)
        assert found is not None
        assert found.ticker_id == ticker_id
        assert found.horizon == "T1"

        not_found = await get_ticket_by_id(db_session, uuid.uuid4())
        assert not_found is None

    async def test_get_tickets_inbox(self, db_session):
        from app.features.conviction_tickets.repository import (
            upsert_tickets,
            get_tickets_inbox,
        )

        ticker_id = uuid.uuid4()
        universe_id = uuid.uuid4()
        inf_run_id = uuid.uuid4()

        await _seed_universe(db_session, universe_id, "test-u4")
        await _seed_ticker(db_session, ticker_id, "INBOX")
        await _seed_inference_run(db_session, inf_run_id, universe_id, date.today())
        await db_session.flush()

        ticket_dicts = [
            {
                "inference_run_id": inf_run_id,
                "ticker_id": ticker_id,
                "universe_id": universe_id,
                "inference_date": date.today(),
                "horizon": "T1",
                "direction": "LONG",
                "predicted_return": 0.02,
                "conviction_score": 80.0,
                "conformal_lower": 0.01,
                "conformal_upper": 0.04,
                "backtest_passes": 3,
                "backtest_pass_strategies": ["mac"],
                "status": "TRADABLE",
                "resolution_date": date.today(),
            },
            {
                "inference_run_id": inf_run_id,
                "ticker_id": ticker_id,
                "universe_id": universe_id,
                "inference_date": date.today(),
                "horizon": "T5",
                "direction": "LONG",
                "predicted_return": 0.03,
                "conviction_score": 90.0,
                "conformal_lower": 0.02,
                "conformal_upper": 0.05,
                "backtest_passes": 4,
                "backtest_pass_strategies": ["mac", "ma_cross", "bb", "rsi"],
                "status": "TRADABLE",
                "resolution_date": date.today(),
            },
        ]
        await upsert_tickets(db_session, ticket_dicts)

        inbox = await get_tickets_inbox(db_session, universe_id=universe_id)
        assert len(inbox) == 2
        assert inbox[0].conviction_score == 90.0
        assert inbox[1].conviction_score == 80.0

    async def test_get_tickets_history(self, db_session):
        from app.features.conviction_tickets.repository import (
            upsert_tickets,
            get_tickets_history,
        )

        ticker_id = uuid.uuid4()
        universe_id = uuid.uuid4()
        inf_run_id = uuid.uuid4()

        await _seed_universe(db_session, universe_id, "test-u5")
        await _seed_ticker(db_session, ticker_id, "HIST")
        await _seed_inference_run(
            db_session, inf_run_id, universe_id, date(2025, 1, 15)
        )
        await db_session.flush()

        ticket_dicts = [
            {
                "inference_run_id": inf_run_id,
                "ticker_id": ticker_id,
                "universe_id": universe_id,
                "inference_date": date(2025, 1, 15),
                "horizon": "T1",
                "direction": "LONG",
                "predicted_return": 0.02,
                "conviction_score": 75.0,
                "conformal_lower": 0.01,
                "conformal_upper": 0.04,
                "backtest_passes": 2,
                "backtest_pass_strategies": ["mac"],
                "status": "REVIEWED",
                "resolution_date": date(2025, 1, 16),
            }
        ]
        await upsert_tickets(db_session, ticket_dicts)

        history = await get_tickets_history(db_session, universe_id=universe_id)
        assert len(history) >= 1

    async def test_get_tickets_for_resolution(self, db_session):
        from app.features.conviction_tickets.repository import (
            upsert_tickets,
            get_tickets_for_resolution,
        )

        ticker_id = uuid.uuid4()
        universe_id = uuid.uuid4()
        inf_run_id = uuid.uuid4()

        past_date = date.today() - timedelta(days=5)
        inf_date = date.today() - timedelta(days=10)

        await _seed_universe(db_session, universe_id, "test-u6")
        await _seed_ticker(db_session, ticker_id, "RESOLVE")
        await _seed_inference_run(db_session, inf_run_id, universe_id, inf_date)
        await db_session.flush()

        ticket_dicts = [
            {
                "inference_run_id": inf_run_id,
                "ticker_id": ticker_id,
                "universe_id": universe_id,
                "inference_date": inf_date,
                "horizon": "T1",
                "direction": "LONG",
                "predicted_return": 0.02,
                "conviction_score": 80.0,
                "conformal_lower": 0.01,
                "conformal_upper": 0.04,
                "backtest_passes": 3,
                "backtest_pass_strategies": ["mac"],
                "status": "TRADABLE",
                "resolution_date": past_date,
            }
        ]
        await upsert_tickets(db_session, ticket_dicts)

        due = await get_tickets_for_resolution(db_session, date.today())
        assert len(due) >= 1

    async def test_update_ticket_status(self, db_session):
        from app.features.conviction_tickets.repository import (
            upsert_tickets,
            update_ticket_status,
        )
        from app.features.conviction_tickets.models import ConvictionTicket
        from sqlalchemy import select

        ticker_id = uuid.uuid4()
        universe_id = uuid.uuid4()
        inf_run_id = uuid.uuid4()

        await _seed_universe(db_session, universe_id, "test-u7")
        await _seed_ticker(db_session, ticker_id, "STATUS")
        await _seed_inference_run(db_session, inf_run_id, universe_id, date.today())
        await db_session.flush()

        ticket_dicts = [
            {
                "inference_run_id": inf_run_id,
                "ticker_id": ticker_id,
                "universe_id": universe_id,
                "inference_date": date.today(),
                "horizon": "T1",
                "direction": "LONG",
                "predicted_return": 0.02,
                "conviction_score": 80.0,
                "conformal_lower": 0.01,
                "conformal_upper": 0.04,
                "backtest_passes": 3,
                "backtest_pass_strategies": ["mac"],
                "status": "TRADABLE",
                "resolution_date": date.today(),
            }
        ]
        await upsert_tickets(db_session, ticket_dicts)

        result = await db_session.execute(
            select(ConvictionTicket).where(
                ConvictionTicket.inference_run_id == inf_run_id
            )
        )
        created = result.scalar_one()

        updated = await update_ticket_status(
            db_session,
            created.id,
            "REVIEWED",
            user_notes="Looks good",
        )
        assert updated is not None
        assert updated.status == "REVIEWED"
        assert updated.user_notes == "Looks good"

    async def test_update_ticket_status_nonexistent(self, db_session):
        from app.features.conviction_tickets.repository import update_ticket_status

        result = await update_ticket_status(db_session, uuid.uuid4(), "REVIEWED")
        assert result is None

    async def test_create_filter_run(self, db_session):
        from app.features.conviction_tickets.repository import create_filter_run

        inf_run_id = uuid.uuid4()
        bt_run_id = uuid.uuid4()
        universe_id = uuid.uuid4()

        await _seed_universe(db_session, universe_id, "test-filter")
        await _seed_inference_run(db_session, inf_run_id, universe_id, date.today())
        await _seed_backtest_run(db_session, bt_run_id, universe_id)
        await db_session.flush()

        fr = await create_filter_run(
            db_session,
            inference_run_id=inf_run_id,
            backtest_run_id=bt_run_id,
            num_evaluated=100,
            num_emitted=15,
            config={"w_max": {0: 0.05}},
        )
        assert fr.id is not None
        assert fr.num_tickets_emitted == 15
        assert fr.num_predictions_evaluated == 100
