dev:
	uv run uvicorn app.app:create_app --factory --reload --loop asyncio

test:
	uv run python -m pytest -m "not integration"

test-integration:
	uv run python -m pytest -m integration

migrate:
	uv run alembic upgrade head

revision:
	uv run alembic revision -m "new migration"
