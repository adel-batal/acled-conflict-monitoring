from pathlib import Path
import logging

from fastapi import (
    FastAPI,
    Depends,
    Query,
    HTTPException,
    BackgroundTasks,
)
from fastapi.responses import JSONResponse

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import SessionLocal, get_db
from app.importer import import_sample_csv_if_empty

from app.auth.jwt import create_access_token
from app.auth.security import hash_password, verify_password
from app.auth.admin_seed import seed_admin_if_configured
from app.auth.deps import get_current_user, require_admin

from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UnauthorizedOut
from app.schemas.conflict import (
    ConflictDataPageOut,
    ConflictCountryGroupOut,
    ConflictRowOut,
)
from app.schemas.risk import RiskScoreOut, CalculatingOut
from app.schemas.feedback import FeedbackIn, FeedbackOut
from app.schemas.delete_conflict import ConflictDeleteIn, DeleteOut
from app.schemas.errors import NotFoundOut, UnprocessableEntityOut, ConflictOut
from app.schemas.meta import HealthOut

from app.models import User, ConflictData, UserFeedback

from app.conflict_queries import (
    fetch_conflictdata_grouped_by_country,
    fetch_conflict_rows_for_countries,
    fetch_conflict_rows_for_country,
)

from app.risk_cache import (
    STATUS_READY,
    STATUS_STALE,
    get_or_create_cache_row,
    try_mark_computing,
    reset_computing_to_failed_on_startup,
)

from app.risk_compute import compute_country_risk_score
from app.core.normalize import norm

from fastapi.security import HTTPBearer



log = logging.getLogger("app")

app = FastAPI(title="ACLED conflicts API", version="0.1.0")

bearer_scheme = HTTPBearer(
    bearerFormat="JWT",
    description="JWT Authorization header using the Bearer scheme. Example: 'Authorization: Bearer <token>'",
)



@app.on_event("startup")
def startup() -> None:
    csv_path = Path("sample_data.csv")
    db = SessionLocal()
    try:
        seed_admin_if_configured(db)
        import_sample_csv_if_empty(db, csv_path)
        reset_computing_to_failed_on_startup(db)
    finally:
        db.close()


@app.get("/health", tags=["meta"], response_model=HealthOut)
def health() -> HealthOut:
    return HealthOut(status="ok")


log = logging.getLogger("app.auth")


def _get_user_by_email(db: Session, email: str) -> User | None:
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


@app.post(
    "/register",
    response_model=TokenOut,
    responses={409: {"model": ConflictOut}},
    tags=["auth"],
)
def register(payload: RegisterIn) -> TokenOut:
    db = SessionLocal()
    try:
        user = User(email=str(payload.email), password_hash=hash_password(payload.password), role="user")
        db.add(user)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            # Don't leak whether an email exists beyond this 409
            return JSONResponse(status_code=409, content={"detail": "email already registered"})
        token = create_access_token(sub=str(user.id), role=user.role)
        return TokenOut(access_token=token)
    finally:
        db.close()


@app.post(
    "/login",
    response_model=TokenOut,
    responses={401: {"model": UnauthorizedOut}},
    tags=["auth"],
)
def login(payload: LoginIn) -> TokenOut:
    db = SessionLocal()
    try:
        user = _get_user_by_email(db, str(payload.email))
        if not user or not verify_password(payload.password, user.password_hash):
            # 401 for bad credentials
            return JSONResponse(status_code=401, content={"detail": "invalid credentials"})
        token = create_access_token(sub=str(user.id), role=user.role)
        return TokenOut(access_token=token)
    finally:
        db.close()


@app.get(
    "/conflictdata",
    response_model=ConflictDataPageOut,
    responses={401: {"model": UnauthorizedOut}},
    tags=["conflictdata"],
    dependencies=[Depends(bearer_scheme)],
)
def list_conflictdata(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ConflictDataPageOut:
    countries = fetch_conflictdata_grouped_by_country(db, page=page, per_page=per_page)
    country_norms = [c[0] for c in countries]

    rows = fetch_conflict_rows_for_countries(db, country_norms)

    # Map norm -> display raw
    country_raw_by_norm = {cn: cr for cn, cr in countries}

    grouped: dict[str, list[ConflictRowOut]] = {}
    for r in rows:
        grouped.setdefault(r.country_norm, []).append(
            ConflictRowOut(
                admin1_raw=r.admin1_raw,
                population=r.population,
                events=r.events,
                score=r.score,
            )
        )

    out = []
    for cn in country_norms:
        out.append(
            ConflictCountryGroupOut(
                country_raw=country_raw_by_norm[cn],
                rows=grouped.get(cn, []),
            )
        )

    return ConflictDataPageOut(page=page, per_page=per_page, countries=out)


@app.get(
    "/conflictdata/{country}",
    response_model=list[ConflictRowOut],
    responses={
        401: {"model": UnauthorizedOut},
        404: {"model": NotFoundOut},
    },
    tags=["conflictdata"],
    dependencies=[Depends(bearer_scheme)],
)
def get_conflictdata_country(
    country: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ConflictRowOut]:
    rows = fetch_conflict_rows_for_country(db, country)
    if not rows:
        raise HTTPException(status_code=404, detail="country not found")

    return [
        ConflictRowOut(
            admin1_raw=r.admin1_raw,
            population=r.population,
            events=r.events,
            score=r.score,
        )
        for r in rows
    ]


@app.get(
    "/conflictdata/{country}/riskscore",
    response_model=RiskScoreOut,
    responses={
        202: {"model": CalculatingOut},
        401: {"model": UnauthorizedOut},
        404: {"model": NotFoundOut},
    },
    tags=["conflictdata"],
    dependencies=[Depends(bearer_scheme)],
)
def get_country_riskscore(
    country: str,
    background: BackgroundTasks,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    country_norm = norm(country)

    # If country doesn't exist at all, return 404
    exists = db.execute(
        select(ConflictData.id).where(ConflictData.country_norm == country_norm).limit(1)
    ).scalar_one_or_none()
    if not exists:
        raise HTTPException(status_code=404, detail="country not found")

    cache = get_or_create_cache_row(db, country)

    if cache.status == STATUS_READY and cache.score is not None:
        return RiskScoreOut(country_norm=cache.country_norm, score=cache.score)

    # stale/failed/computing => ensure job is enqueued
    should_compute = try_mark_computing(db, cache.country_norm)
    if should_compute:
        background.add_task(compute_country_risk_score, cache.country_norm)

    return JSONResponse(status_code=202, content={"detail": "calculating"})

@app.post(
    "/conflictdata/{admin1}/userfeedback",
    response_model=FeedbackOut,
    responses={
        401: {"model": UnauthorizedOut},
        404: {"model": NotFoundOut},
        422: {"model": UnprocessableEntityOut},
    },
    tags=["feedback"],
    dependencies=[Depends(bearer_scheme)],
)
def create_user_feedback(
    admin1: str,
    payload: FeedbackIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FeedbackOut:
    feedback_text = payload.feedback.strip()
    if len(feedback_text) < 10 or len(feedback_text) > 500:
        raise HTTPException(status_code=422, detail="feedback must be 10-500 chars after trim")

    country_norm = norm(payload.country)
    admin1_norm = norm(admin1)

    conflict = db.execute(
        select(ConflictData).where(
            ConflictData.country_norm == country_norm,
            ConflictData.admin1_norm == admin1_norm,
        )
    ).scalar_one_or_none()

    if not conflict:
        raise HTTPException(status_code=404, detail="conflict_data row not found for country+admin1")

    fb = UserFeedback(
        user_id=user.id,
        conflict_data_id=conflict.id,
        feedback_text=feedback_text,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)

    # Logging: metadata only (no JWT, no feedback body)
    logging.getLogger("app.feedback").info(
        "feedback_created",
        extra={"user_id": user.id, "conflict_data_id": conflict.id, "country_norm": country_norm},
    )

    return FeedbackOut(id=fb.id, conflict_data_id=fb.conflict_data_id)


@app.delete(
    "/conflictdata",
    tags=["conflictdata"],
    response_model=DeleteOut,
    responses={
        401: {"model": UnauthorizedOut},
        404: {"model": NotFoundOut},
    },
    dependencies=[Depends(bearer_scheme)],
)
def delete_conflictdata(
    payload: ConflictDeleteIn,
    background: BackgroundTasks,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> DeleteOut:
    country_norm = norm(payload.country)
    admin1_norm = norm(payload.admin1)

    # Transaction: delete + mark stale
    with db.begin():
        conflict = db.execute(
            select(ConflictData).where(
                ConflictData.country_norm == country_norm,
                ConflictData.admin1_norm == admin1_norm,
            )
        ).scalar_one_or_none()

        if not conflict:
            raise HTTPException(status_code=404, detail="conflict_data row not found")

        db.delete(conflict)

        cache = get_or_create_cache_row(db, payload.country)
        cache.status = STATUS_STALE
        cache.score = None
        cache.computed_at = None
        cache.last_error = None

    # After commit: enqueue compute
    # Need a fresh DB session state for marking computing; reuse same session is OK.
    should_compute = try_mark_computing(db, country_norm)
    if should_compute:
        background.add_task(compute_country_risk_score, country_norm)

    logging.getLogger("app.conflictdata").info(
        "conflictdata_deleted",
        extra={"country_norm": country_norm, "admin1_norm": admin1_norm},
    )

    return DeleteOut(detail="deleted")