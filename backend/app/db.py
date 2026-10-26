from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


engine = create_engine(
    get_settings().database_url,
    pool_pre_ping=True,
    pool_timeout=5,
    connect_args={"options": "-c timezone=UTC", "connect_timeout": 5},
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def get_db():
    with SessionLocal() as db:
        try:
            yield db
            db.commit()
            from app.services.privacy import mark_completed

            for path in db.info.pop("privacy_events", []):
                try:
                    mark_completed(path)
                except OSError:
                    # The durable pending event will be retried by maintenance.
                    pass
        except Exception:
            db.rollback()
            raise
