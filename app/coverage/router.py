# Feature 5 · Desk coverage | Owner: Aarya Patel
# AI disclosure: with guidance of Claude (Anthropic).
# Product v1 (Deliverable 2): E9 · Keep the desk covered (US-26 to US-29) and US-33 supervisor notifications.
# E10 (US-30 to US-32, the public coverage page and desk hours) comes in Product v2; E11 (time away) in the final product.
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth.deps import current_staff
from app.auth.models import ROLE_LEAD, ROLE_SUPERVISOR, Staff
from app.core import clock
from app.core.database import get_db
from app.core.realtime import hub

from . import logic, notify
from .models import LABELS, SupervisorNotification

router = APIRouter(prefix="/api", tags=["Feature 5 · Desk coverage (Aarya)"])


class StatusIn(BaseModel):
    status: str
    back_at: str | None = Field(default=None, description="Local time like 13:15, for break / lunch / stepped away")
    confirm_empty: bool = False   # US-28: "Yes, leave the desk unattended"


def _status_out(s, now) -> dict:
    return {"status": s.status, "label": LABELS[s.status], "since": s.since, "back_at": s.back_at,
            "overdue": bool(s.back_at and s.back_at < now)}


def _email_supervisors(db: Session, note: SupervisorNotification, background: BackgroundTasks) -> None:
    if not notify.email_enabled():
        return
    emails = [e for e in db.scalars(select(Staff.email).where(Staff.role == ROLE_SUPERVISOR, Staff.active,
                                                              Staff.email.is_not(None))).all() if e]
    if emails:
        note.emailed = True
        db.commit()
        background.add_task(notify.send_email, emails, note.message, note.at)


# ---------- E9 · Keep the desk covered (staff) ----------

@router.get("/status/me")
def my_status(me: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    now = clock.utcnow()
    s = logic.status_of(db, me, now)
    db.commit()
    return _status_out(s, now)


@router.patch("/status/me")
def set_my_status(body: StatusIn, background: BackgroundTasks, me: Staff = Depends(current_staff),
                  db: Session = Depends(get_db)):
    """US-26 set my status; US-28 warn before leaving the desk empty; US-33 notify the supervisor."""
    now = clock.utcnow()
    try:
        back_at = logic.parse_back_at(body.back_at, now)
        s, note = logic.set_status(db, me, body.status, back_at, body.confirm_empty, now)
    except logic.LastOnDesk as warn:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(warn))
    except ValueError as bad:
        db.rollback()
        raise HTTPException(422, str(bad))
    background.add_task(hub.broadcast, "status")
    if note is not None:
        _email_supervisors(db, note, background)
        background.add_task(hub.broadcast, "notifications")
    return _status_out(s, now)


@router.get("/status/board")
def coverage_board(_: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-27 + US-29: staff-only board with names."""
    return logic.board(db, clock.utcnow())


# ---------- US-33 · Staff notifications ----------
# Every signed-in staff member can read the feed (test 4). The unread list and "Mark all as read"
# belong to the supervisor and shift leads, so an assistant can't clear the supervisor's unread items.
# Only supervisors are emailed (test 5).

def _is_senior(me: Staff) -> bool:
    return me.role in (ROLE_SUPERVISOR, ROLE_LEAD)


def _senior_only(me: Staff = Depends(current_staff)) -> Staff:
    if not _is_senior(me):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the supervisor and shift leads can mark notifications as read.")
    return me


@router.get("/notifications")
def notifications(day: date | None = Query(None, description="Local date; defaults to today"),
                  me: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """Every check-in, check-out, break, lunch and return for one day, newest first, with times.
    Open to all staff; the unread count is only for the supervisor and shift leads."""
    now = clock.utcnow()
    d = day or clock.local_date(now)
    start, end = clock.local_midnight_utc(d), clock.local_midnight_utc(d.fromordinal(d.toordinal() + 1))
    rows = db.scalars(select(SupervisorNotification).where(SupervisorNotification.at >= start,
                                                           SupervisorNotification.at < end)
                      .order_by(SupervisorNotification.at.desc(), SupervisorNotification.id.desc())).all()
    senior = _is_senior(me)
    unread = (db.scalar(select(func.count()).select_from(SupervisorNotification)
                        .where(SupervisorNotification.read_at.is_(None))) or 0) if senior else 0
    return {"day": d, "unread": unread, "can_mark_read": senior, "email_enabled": notify.email_enabled(),
            "items": [{"id": n.id, "staff_name": n.staff_name, "kind": n.kind, "message": n.message,
                       "at": n.at, "time": clock.fmt_time(n.at), "read": n.read_at is not None,
                       "emailed": n.emailed} for n in rows]}


@router.post("/notifications/read")
def mark_all_read(background: BackgroundTasks, _: Staff = Depends(_senior_only), db: Session = Depends(get_db)):
    db.execute(update(SupervisorNotification).where(SupervisorNotification.read_at.is_(None))
               .values(read_at=clock.utcnow()))
    db.commit()
    background.add_task(hub.broadcast, "notifications")
    return {"ok": True}
