from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import ConflictData
from app.risk_cache import mark_failed, mark_ready

log = logging.getLogger("app.riskscore")


def compute_country_risk_score(country_norm: str) -> None:
    """
    Runs in background. Must not raise.
    """
    log.info("starting risk score compute", extra={"country_norm": country_norm})
    db: Session = SessionLocal()
    try:
        log.info("querying for avg score", extra={"country_norm": country_norm})
        avg_score = db.execute(
            select(func.avg(ConflictData.score)).where(ConflictData.country_norm == country_norm)
        ).scalar_one_or_none()
        log.info("got avg score", extra={"country_norm": country_norm, "avg_score": avg_score})

        if avg_score is None:
            mark_failed(db, country_norm, "no rows for country")
            return

        score = avg_score if isinstance(avg_score, Decimal) else Decimal(str(avg_score))
        mark_ready(db, country_norm, score)
        log.info("risk score compute complete", extra={"country_norm": country_norm})
    except Exception as e:
        log.exception("risk score compute failed", extra={"country_norm": country_norm})
        try:
            mark_failed(db, country_norm, str(e))
        except Exception:
            log.exception("failed to mark failed", extra={"country_norm": country_norm})
    finally:
        db.close()
