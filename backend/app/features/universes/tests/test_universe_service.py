"""CRUD service tests for universes — TDD: functions do NOT exist yet.

These tests MUST fail (RED phase) before the implementation is written.
"""

import uuid

import pytest

from app.features.universes.models import Universe


def _make_system_universe(db) -> Universe:
    universe = Universe(
        name="sp500",
        display_name="S&P 500",
        description="S&P 500 system index",
        is_system_managed=True,
        public_id="uni_sys01",
    )
    db.add(universe)
    return universe


def _make_custom_universe(db, name: str = "custom-test") -> Universe:
    universe = Universe(
        name=name,
        display_name="Custom Test",
        description="A custom universe",
        public_id="uni_custom01",
    )
    db.add(universe)
    return universe


# ---- Tests that MUST FAIL (TDD RED phase) ----


@pytest.mark.asyncio
async def test_create_custom_universe(db_session):
    from app.features.universes import service as universes_service

    universe = await universes_service.create_universe(
        db_session,
        name="my-custom-universe",
        display_name="My Custom Universe",
        description="Test description",
    )
    assert uuid.UUID(str(universe.id))
    assert universe.public_id is not None
    assert universe.public_id.startswith("uni_")
    assert universe.name == "my-custom-universe"
    assert universe.display_name == "My Custom Universe"
    assert universe.description == "Test description"
    assert universe.is_system_managed is False


@pytest.mark.asyncio
async def test_create_duplicate_name_raises(db_session):
    from app.features.universes import service as universes_service

    await universes_service.create_universe(
        db_session,
        name="dup-universe",
        display_name="Duplicate Universe",
    )
    with pytest.raises(ValueError, match="already exists"):
        await universes_service.create_universe(
            db_session,
            name="dup-universe",
            display_name="Another Duplicate",
        )


@pytest.mark.asyncio
async def test_update_universe_metadata(db_session):
    from app.features.universes import service as universes_service

    universe = _make_custom_universe(db_session)
    await db_session.flush()

    updated = await universes_service.update_universe(
        db_session,
        universe_id=universe.id,
        name="updated-name",
        display_name="Updated Display",
        description="Updated description",
    )
    assert updated.name == "updated-name"
    assert updated.display_name == "Updated Display"
    assert updated.description == "Updated description"


@pytest.mark.asyncio
async def test_soft_delete_universe(db_session):
    from app.features.universes import service as universes_service
    from app.features.universes import repository as universes_repo

    universe = _make_custom_universe(db_session)
    await db_session.flush()

    await universes_service.soft_delete_universe(db_session, universe.id)
    await db_session.flush()

    deleted_universe = await universes_repo.get_universe_by_id(
        db_session, universe.id, include_deleted=True
    )
    assert deleted_universe is not None
    assert deleted_universe.deleted_at is not None

    active_universe = await universes_repo.get_universe_by_id(db_session, universe.id)
    assert active_universe is None


@pytest.mark.asyncio
async def test_list_includes_deleted_with_flag(db_session):
    from app.features.universes import service as universes_service

    active = _make_custom_universe(db_session, name="active-unique-test")
    deleted = _make_custom_universe(db_session, name="deleted-unique-test")
    await db_session.flush()

    await universes_service.soft_delete_universe(db_session, deleted.id)
    await db_session.flush()

    default_list = await universes_service.list_universes(db_session)
    active_ids = {u.id for u in default_list.universes}
    assert active.id in active_ids
    assert deleted.id not in active_ids

    with_deleted = await universes_service.list_universes(
        db_session, include_deleted=True
    )
    all_ids = {u.id for u in with_deleted.universes}
    assert active.id in all_ids
    assert deleted.id in all_ids


@pytest.mark.asyncio
async def test_cannot_delete_system_managed(db_session):
    from app.features.universes import service as universes_service

    sys_universe = _make_system_universe(db_session)
    await db_session.flush()

    with pytest.raises(ValueError, match="system-managed"):
        await universes_service.soft_delete_universe(db_session, sys_universe.id)


@pytest.mark.asyncio
async def test_cannot_rename_system_managed(db_session):
    from app.features.universes import service as universes_service

    sys_universe = _make_system_universe(db_session)
    await db_session.flush()

    with pytest.raises(ValueError, match="system-managed"):
        await universes_service.update_universe(
            db_session,
            universe_id=sys_universe.id,
            name="hacked-name",
        )
