from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="user")


class ConflictData(Base):
    __tablename__ = "conflict_data"
    __table_args__ = (
        UniqueConstraint("country_norm", "admin1_norm", name="uq_conflict_country_admin1_norm"),
        CheckConstraint("events >= 0", name="ck_conflict_events_nonneg"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    country_raw: Mapped[str] = mapped_column(String(50), nullable=False)
    country_norm: Mapped[str] = mapped_column(String(50), index=True, nullable=False)

    admin1_raw: Mapped[str] = mapped_column(String(50), nullable=False)
    admin1_norm: Mapped[str] = mapped_column(String(50), index=True, nullable=False)

    population: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    events: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)

    feedback: Mapped[list["UserFeedback"]] = relationship(back_populates="conflict_data")


class UserFeedback(Base):
    __tablename__ = "user_feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    conflict_data_id: Mapped[int] = mapped_column(
        ForeignKey("conflict_data.id", ondelete="CASCADE"), nullable=False
    )

    feedback_text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    conflict_data: Mapped["ConflictData"] = relationship(back_populates="feedback")


class RiskScoreCache(Base):
    __tablename__ = "risk_score_cache"
    __table_args__ = (UniqueConstraint("country_norm", name="uq_risk_country_norm"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    country_norm: Mapped[str] = mapped_column(String(50), nullable=False)

    # keep as text for now (computing/ready/failed/stale). We'll treat as enum-in-code.
    status: Mapped[str] = mapped_column(String(20), nullable=False)

    score: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    computed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
