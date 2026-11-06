# Feature 1 · Walk-up queue | Owner: Mohit Sawant
# AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the owner.
"""Rules of the line. Kept separate from the routes so they're easy to test."""
import re
from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import DEFAULT_VISIT_MINUTES, MISSED_CALL_MINUTES, RECENT_CALL_MINUTES

from .models import CALLED, DONE, GONE, WAITING, Visit

_NAME_OK = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ' .-]*$")


def check_first_name(raw: str) -> str:
    """US-01: first name only. Anything with a digit looks like an NSID (abc123) or a
    student number (11223344), so it is refused rather than stored."""
    name = " ".join((raw or "").split())
    if not name:
        raise ValueError("Please type your first name.")
    if any(ch.isdigit() for ch in name) or not _NAME_OK.match(name) or len(name) > 40:
        raise ValueError("Please enter your first name only.")
    return name


def sweep_missed(db: Session, now: datetime | None = None) -> int:
    """US-06: a called student who hasn't reached the counter within 5 minutes is marked Gone,
    so the counter can call the next person. Run before reading or changing the line."""
    now = now or clock.utcnow()
    cutoff = now - timedelta(minutes=MISSED_CALL_MINUTES)
    missed = db.scalars(select(Visit).where(Visit.status == CALLED, Visit.called_at <= cutoff)).all()
    for v in missed:
        v.status = GONE
        v.finished_at = v.called_at + timedelta(minutes=MISSED_CALL_MINUTES)
    if missed:
        db.commit()
    return len(missed)


def next_ticket_no(db: Session, now: datetime) -> int:
    today = clock.local_date(now)
    last = db.scalar(select(func.max(Visit.ticket_no)).where(Visit.ticket_date == today))
    return (last or 0) + 1


def waiting_line(db: Session) -> list[Visit]:
    """Everyone still waiting, longest wait first (US-04)."""
    return list(db.scalars(select(Visit).where(Visit.status == WAITING)
                           .order_by(Visit.arrived_at, Visit.id)).all())


def service_rate(db: Session, now: datetime) -> float:
    """Average minutes per finished visit today. Used only inside the estimate, never shown."""
    start = clock.local_midnight_utc(clock.local_date(now))
    rows = db.execute(select(Visit.served_at, Visit.finished_at)
                      .where(Visit.status == DONE, Visit.finished_at >= start, Visit.served_at.is_not(None))).all()
    lengths = [(f - s).total_seconds() / 60 for s, f in rows]
    return sum(lengths) / len(lengths) if lengths else float(DEFAULT_VISIT_MINUTES)


def counters_calling(db: Session, now: datetime) -> int:
    """How many counters have called someone in the last 30 minutes (US-02).
    This is the queue's own data, so the estimate doesn't depend on any other feature."""
    since = now - timedelta(minutes=RECENT_CALL_MINUTES)
    return db.scalar(select(func.count(func.distinct(Visit.counter))).where(Visit.called_at >= since)) or 0


def estimate_minutes(ahead: int, rate: float, counters: int) -> int | None:
    """People ahead x minutes per visit / counters calling. None means "can't estimate right now"."""
    if counters == 0:
        return None
    return round(ahead * rate / counters)


def claim_next(db: Session, counter: str, now: datetime) -> Visit | None:
    """US-04: call the student who has waited longest.

    Two counters can press Call next at the same instant. The UPDATE only succeeds if the visit
    is still waiting, and the database applies one UPDATE at a time, so only one counter wins.
    The loser simply tries the next person in line.
    """
    for candidate in waiting_line(db):
        result = db.execute(update(Visit)
                            .where(Visit.id == candidate.id, Visit.status == WAITING)
                            .values(status=CALLED, counter=counter, called_at=now))
        db.commit()
        if result.rowcount == 1:
            db.refresh(candidate)
            return candidate
    return None
