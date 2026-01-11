from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.core.config import settings
from app.models import User


def seed_admin_if_configured(db: Session) -> None:
    if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
        return

    existing = db.execute(
        select(User).where(User.email == settings.ADMIN_EMAIL)
    ).scalar_one_or_none()

    if existing:
        return

    admin = User(
        email=settings.ADMIN_EMAIL,
        password_hash=hash_password(settings.ADMIN_PASSWORD),
        role="admin",
    )
    db.add(admin)
    db.commit()
