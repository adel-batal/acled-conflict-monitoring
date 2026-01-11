from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConflictData
from sqlalchemy import select, func

from sqlalchemy import select

from app.core.normalize import norm

def fetch_conflictdata_grouped_by_country(
    db: Session,
    *,
    page: int,
    per_page: int,
) -> list[tuple[str, str]]:
    """
    Returns a list of (country_norm, country_raw) for the requested page,
    ordered alphabetically by country_norm.
    """
    if page < 1:
        page = 1
    if per_page < 1:
        per_page = 20

    # subq = (
    #     select(ConflictData.country_norm, ConflictData.country_raw)
    #     .distinct(ConflictData.country_norm)
    #     .order_by(ConflictData.country_norm.asc())
    #     .limit(per_page)
    #     .offset((page - 1) * per_page)
    # )
    # replaced with the following because This relies on Postgres behavior for distinct(column) + selecting another column. To avoid edge cases, we should do a safer query with min(country_raw) grouped by country_norm. That’s slightly more lines but more correct

    subq = (
        select(
            ConflictData.country_norm,
            func.min(ConflictData.country_raw).label("country_raw"),
        )
        .group_by(ConflictData.country_norm)
        .order_by(ConflictData.country_norm.asc())
        .limit(per_page)
        .offset((page - 1) * per_page)
    )
    return list(db.execute(subq).all())


def fetch_conflict_rows_for_countries(
    db: Session,
    country_norms: list[str],
):
    if not country_norms:
        return []

    q = (
        select(ConflictData)
        .where(ConflictData.country_norm.in_(country_norms))
        .order_by(ConflictData.country_norm.asc(), ConflictData.admin1_norm.asc())
    )
    return list(db.execute(q).scalars().all())

def fetch_conflict_rows_for_country(db: Session, country: str):
    country_norm = norm(country)
    q = (
        select(ConflictData)
        .where(ConflictData.country_norm == country_norm)
        .order_by(ConflictData.admin1_norm.asc())
    )
    return list(db.execute(q).scalars().all())
