"""SQLAlchemy ORM models for the universes feature.

Tables: universes, tickers, universe_memberships.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.features.core.base import Base, SoftDeletable, Timestamped, UUIDPrimaryKey


class Universe(Base, UUIDPrimaryKey, Timestamped, SoftDeletable):
    __tablename__ = "universes"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system_managed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    memberships: Mapped[list["UniverseMembership"]] = relationship(
        "UniverseMembership", back_populates="universe", cascade="all, delete-orphan"
    )

    __table_args__ = (UniqueConstraint("name", name="uq_universes_name"),)


class Ticker(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "tickers"

    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(50), nullable=True)
    asset_type: Mapped[str] = mapped_column(
        String(20), default="equity", server_default="'equity'"
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class UniverseMembership(Base, UUIDPrimaryKey):
    __tablename__ = "universe_memberships"

    universe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("universes.id", ondelete="CASCADE"),
        nullable=False,
    )
    ticker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tickers.id", ondelete="CASCADE"),
        nullable=False,
    )
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    universe: Mapped["Universe"] = relationship(
        "Universe", back_populates="memberships"
    )
    ticker: Mapped["Ticker"] = relationship("Ticker")

    __table_args__ = (
        UniqueConstraint(
            "universe_id",
            "ticker_id",
            "added_at",
            name="uq_universe_memberships_universe_ticker_added",
        ),
    )
