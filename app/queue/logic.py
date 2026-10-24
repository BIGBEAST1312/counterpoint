# Feature 1 (E1): rules of the line, kept apart from the routes so they are easy to test | Owner: Mohit Sawant
import re
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import DEFAULT_VISIT_MINUTES, RECENT_CALL_MINUTES

from .models import DONE, WAITING, Visit

_LETTERS_ONLY = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ' .-]*$")


def check_first_name(raw: str) -> str:
    """US-01: first name only. A digit means it looks like an NSID or student number, so refuse it."""
    name = " ".join((raw or "").split())
    if not name:
        raise ValueError("Please type your first name.")
    if any(c.isdigit() for c in name) or len(name) > 40 or not _LETTERS_ONLY.match(name):
        raise ValueError("Please enter your first name only.")
    return name


def next_ticket_no(db: Session, now: datetime) -> int:
    """US-01: today's next number. It starts again at 1 each local day."""
    last = db.scalar(select(func.max(Visit.ticket_no)).where(Visit.ticket_date == clock.local_date(now)))
    return (last or 0) + 1


def waiting_line(db: Session) -> list[Visit]:
    """Everyone still waiting, the one who arrived first at the top."""
    return list(db.scalars(select(Visit).where(Visit.status == WAITING).order_by(Visit.arrived_at, Visit.id)))


def minutes_per_visit(db: Session, now: datetime) -> float:
    """US-02: average length of today's finished visits, or the default when none have finished."""
    start = clock.local_midnight_utc(clock.local_date(now))
    rows = db.execute(select(Visit.served_at, Visit.finished_at).where(
        Visit.status == DONE, Visit.finished_at >= start, Visit.served_at.is_not(None))).all()
    lengths = [(end - begin).total_seconds() / 60 for begin, end in rows]
    return sum(lengths) / len(lengths) if lengths else float(DEFAULT_VISIT_MINUTES)


def counters_calling(db: Session, now: datetime) -> int:
    """US-02: how many counters called someone in the last 30 minutes."""
    since = now - timedelta(minutes=RECENT_CALL_MINUTES)
    return db.scalar(select(func.count(func.distinct(Visit.counter))).where(Visit.called_at >= since)) or 0


def estimate(db: Session, ahead: int, now: datetime) -> int | None:
    """US-02: people ahead x minutes per visit / counters calling. None = can't estimate right now."""
    counters = counters_calling(db, now)
    if counters == 0:
        return None
    return round(ahead * minutes_per_visit(db, now) / counters)


def wait_text(minutes: int | None) -> str:
    if minutes is None:
        return "The wait can't be estimated right now. You still have your place in line."
    if minutes == 0:
        return "You're next."
    return f"About {minutes} minutes."
