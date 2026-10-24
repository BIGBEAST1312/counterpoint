# Feature 5 · Desk coverage | Owner: Aarya Patel
# AI disclosure: with guidance of Claude (Anthropic).
"""Rules for staff status and the coverage board. (The public coverage page and desk hours come in Product v2.)"""
import re
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import Staff
from app.core import clock

from . import notify
from .models import AWAY, LABELS, OFF_SHIFT, ON_DESK, StaffStatus, StatusEvent, SupervisorNotification

_HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def sentence(text: str) -> str:
    """End with exactly one full stop, even after 'a.m.' or 'p.m.'."""
    return text if text.endswith(".") else text + "."


class LastOnDesk(Exception):
    """US-28: the last person on desk is about to leave it empty."""


def status_of(db: Session, staff: Staff, now: datetime) -> StaffStatus:
    s = db.get(StaffStatus, staff.id)
    if s is None:
        s = StaffStatus(staff_id=staff.id, status=OFF_SHIFT, since=now)
        db.add(s)
        db.flush()
    return s


def on_desk(db: Session) -> list[StaffStatus]:
    return list(db.scalars(select(StaffStatus).where(StaffStatus.status == ON_DESK)
                           .order_by(StaffStatus.since)).all())


def parse_back_at(hhmm: str | None, now: datetime) -> datetime | None:
    if not hhmm:
        return None
    if not _HHMM.match(hhmm.strip()):
        raise ValueError("Back-at time must look like 13:15.")
    back = clock.local_at(clock.local_date(now), hhmm.strip())
    if back <= now:
        raise ValueError(f"{clock.fmt_time(back)} has already passed. Pick a later back-at time.")
    return back


def set_status(db: Session, me: Staff, new: str, back_at: datetime | None, confirm_empty: bool,
               now: datetime) -> tuple[StaffStatus, SupervisorNotification | None]:
    """US-26 + US-28 + US-33. Returns the new status and the supervisor notification (if anything changed)."""
    if new not in LABELS:
        raise ValueError("Status must be On desk, On break, At lunch, Stepped away or Off shift.")
    current = status_of(db, me, now)
    old = current.status
    if new != ON_DESK and old == ON_DESK and not confirm_empty:
        others = [s for s in on_desk(db) if s.staff_id != me.id]
        if not others:
            raise LastOnDesk("You're the only one on desk. The desk will show as unattended.")
    new_back = back_at if new in AWAY else None
    if new == old and new_back == current.back_at:
        return current, None  # nothing changed: no event, no notification
    if new != old:
        current.status, current.since = new, now
        if new == ON_DESK:
            current.on_desk_stretch_from = now   # break planner counts from here (US-29 test 3)
        elif new == OFF_SHIFT:
            current.on_desk_stretch_from = None
    current.back_at = new_back
    event = StatusEvent(staff_id=me.id, from_status=old, to_status=new, at=now, back_at=new_back)
    db.add(event)
    db.flush()
    note = None
    if new != old:
        kind, message = notify.describe(me.display_name, old, new, now, new_back)
        note = SupervisorNotification(event_id=event.id, staff_name=me.display_name, kind=kind,
                                      message=message, at=now)
        db.add(note)
    db.commit()
    return current, note


def board(db: Session, now: datetime) -> dict:
    """US-27 + US-29: who is on desk, who is away, and who should take a break next."""
    rows = db.scalars(select(StaffStatus).where(StaffStatus.status != OFF_SHIFT)).all()
    desk = sorted((s for s in rows if s.status == ON_DESK), key=lambda s: s.since)
    away = sorted((s for s in rows if s.status in AWAY), key=lambda s: s.since)
    suggestion = None
    if len(desk) >= 2:  # only suggest a break if the desk stays covered (US-29 test 2)
        nxt = min(desk, key=lambda s: s.on_desk_stretch_from or s.since)
        start = nxt.on_desk_stretch_from or nxt.since
        suggestion = {"staff_id": nxt.staff_id, "name": nxt.staff.display_name, "on_since": start,
                      "message": f"Next break: {nxt.staff.display_name} (on since {clock.fmt_time(start)})"}
    return {
        "on_desk": [{"staff_id": s.staff_id, "name": s.staff.display_name, "since": s.since} for s in desk],
        "away": [{"staff_id": s.staff_id, "name": s.staff.display_name, "status": s.status,
                  "label": LABELS[s.status], "since": s.since, "back_at": s.back_at,
                  "overdue": bool(s.back_at and s.back_at < now)} for s in away],
        "alone": len(desk) == 1,
        "break_suggestion": suggestion,
    }
