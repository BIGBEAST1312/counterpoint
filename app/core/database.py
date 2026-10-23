# Shared infrastructure | Built by Mohit Sawant, owned by no feature
# AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the team.
"""Database connection shared by all five features.

Each feature defines its own tables in its own models.py, all inheriting from `Base`.
Routes get a database session through `Depends(get_db)`.
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.types import TypeDecorator

from .config import DATABASE_URL

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator):
    """Stores datetimes as UTC and always hands them back timezone-aware.

    SQLite forgets time zones, so without this the API would return times the
    browser reads as local time and every wait would be off by six hours.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetime: use app.core.clock.utcnow()")
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect):
        return None if value is None else value.replace(tzinfo=timezone.utc)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Feature packages, in the order they are wired in. A missing one is skipped (see import_feature).
FEATURES = ["queue", "tickets", "guides", "report", "coverage"]


def import_feature(feature: str, module: str):
    """Import app.<feature>.<module>, or return None if that feature hasn't been merged yet.
    Only a missing feature folder is skipped; any other import error still fails loudly."""
    import importlib
    import logging
    try:
        return importlib.import_module(f"app.{feature}.{module}")
    except ModuleNotFoundError as missing:
        feature_packages = {f"app.{f}" for f in FEATURES} | {f"app.{f}.{module}" for f in FEATURES}
        if missing.name in feature_packages:
            if missing.name == f"app.{feature}":
                logging.getLogger("counterpoint").warning("Feature %r isn't merged yet; skipping it.", feature)
            return None
        raise


def init_db(bind=None) -> None:
    """Create any missing tables. Importing the models registers them on Base."""
    from app.auth import models as _auth  # noqa: F401
    for feature in FEATURES:
        import_feature(feature, "models")   # the report has no models of its own: skipped quietly

    Base.metadata.create_all(bind=bind or engine)
