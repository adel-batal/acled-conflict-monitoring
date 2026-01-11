from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.normalize import norm
from app.models import RiskScoreCache
from sqlalchemy.dialects.postgresql import insert

STATUS_COMPUTING = "computing"
STATUS_READY = "ready"
STATUS_FAILED = "failed"
STATUS_STALE = "stale"


def reset_computing_to_failed_on_startup(db: Session) -> int:
    res = db.execute(
        update(RiskScoreCache)
        .where(RiskScoreCache.status == STATUS_COMPUTING)
        .values(status=STATUS_FAILED, last_error="startup reset from computing")
    )
    db.commit()
    return int(res.rowcount or 0)


def get_or_create_cache_row(db: Session, country_norm: str) -> RiskScoreCache:
    """
    Given a normalized country, ensures a cache row exists and returns it.
    Uses a fast/non-locking ON CONFLICT DO NOTHING to avoid race conditions.
    """
    stmt = (
        insert(RiskScoreCache)
        .values(country_norm=country_norm, status=STATUS_STALE)
        .on_conflict_do_nothing(index_elements=[RiskScoreCache.country_norm])
    )
    db.execute(stmt)

    return db.execute(
        select(RiskScoreCache).where(RiskScoreCache.country_norm == country_norm)
    ).scalar_one()



def try_mark_computing(db: Session, country_norm: str) -> bool:
    """
    Returns True if we transitioned into 'computing' (meaning caller should compute),
    False if it was already computing.
    """
    row = db.execute(
        select(RiskScoreCache).where(RiskScoreCache.country_norm == country_norm)
    ).scalar_one()

    if row.status == STATUS_COMPUTING:
        return False

    row.status = STATUS_COMPUTING
    row.last_error = None
    db.commit()
    return True


def mark_ready(db: Session, country_norm: str, score: Decimal) -> None:
    row = db.execute(
        select(RiskScoreCache).where(RiskScoreCache.country_norm == country_norm)
    ).scalar_one()
    row.status = STATUS_READY
    row.score = score
    row.computed_at = datetime.now(timezone.utc)
    row.last_error = None
    db.commit()


def mark_failed(db: Session, country_norm: str, err: str) -> None:
    row = db.execute(
        select(RiskScoreCache).where(RiskScoreCache.country_norm == country_norm)
    ).scalar_one()
    row.status = STATUS_FAILED
    row.last_error = err[:2000]
    db.commit()
