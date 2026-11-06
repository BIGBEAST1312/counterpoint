# Feature 5 · Desk coverage | Owner: Aarya Patel
# AI disclosure: with guidance of Claude (Anthropic).
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.auth.deps import current_staff, senior_only
from app.auth.models import ROLE_SUPERVISOR, Staff
from app.core import clock
from app.core.database import get_db
from app.core.realtime import hub

from . import logic, notify, timeaway
from .models import LABELS, ClosedDay, DeskHours, SupervisorNotification

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
    emails = _supervisor_emails(db)
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


# ---------- E10 · Is the IT desk covered? (public, no sign-in) ----------

@router.get("/coverage")
def public_coverage(db: Session = Depends(get_db)):
    """US-30 to US-32. Counts and times only, never a name."""
    return logic.coverage(db, clock.utcnow())


class HoursIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    opens: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    closes: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class ClosedIn(BaseModel):
    day: date
    reason: str = Field(default="", max_length=80)


@router.put("/desk-hours")
def set_hours(body: list[HoursIn], background: BackgroundTasks, _: Staff = Depends(senior_only),
              db: Session = Depends(get_db)):
    for h in body:
        if (h.opens is None) != (h.closes is None) or (h.opens and h.opens >= h.closes):
            raise HTTPException(422, "Opening time must be before closing time.")
        row = db.get(DeskHours, h.weekday) or DeskHours(weekday=h.weekday)
        row.opens, row.closes = h.opens, h.closes
        db.add(row)
    db.commit()
    background.add_task(hub.broadcast, "status")
    return logic.week_hours(db, clock.utcnow())


@router.post("/desk-hours/closed", status_code=status.HTTP_201_CREATED)
def add_closed_day(body: ClosedIn, background: BackgroundTasks, _: Staff = Depends(senior_only),
                   db: Session = Depends(get_db)):
    row = db.get(ClosedDay, body.day) or ClosedDay(day=body.day)
    row.reason = body.reason.strip()
    db.add(row)
    db.commit()
    background.add_task(hub.broadcast, "status")
    return {"day": row.day, "reason": row.reason}


@router.delete("/desk-hours/closed/{day}", status_code=status.HTTP_204_NO_CONTENT)
def remove_closed_day(day: date, background: BackgroundTasks, _: Staff = Depends(senior_only),
                      db: Session = Depends(get_db)):
    row = db.get(ClosedDay, day)
    if row:
        db.delete(row)
        db.commit()
        background.add_task(hub.broadcast, "status")


# ---------- US-33 · Staff notifications ----------
# Every signed-in staff member can read the feed (test 4). The unread list and "Mark all as read"
# belong to the supervisor and shift leads, so an assistant can't clear the supervisor's unread items.
# Only supervisors are emailed (test 5).

def _senior_only(me: Staff = Depends(current_staff)) -> Staff:
    if not timeaway.is_senior(me):
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
    senior = timeaway.is_senior(me)
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


# ---------- E11 · Time away from the desk (US-34 to US-37) ----------

class AbsenceIn(BaseModel):
    kind: str = Field(description="sick or emergency")
    day: date
    starts: str = Field(description="Shift start, local time like 13:00")
    ends: str = Field(description="Shift end, local time like 17:00")
    note: str = ""


class TimeOffIn(BaseModel):
    start: date
    end: date
    reason: str


class DecisionIn(BaseModel):
    approve: bool
    reason: str = ""


def _supervisor_emails(db: Session) -> list[str]:
    return [e for e in db.scalars(select(Staff.email).where(Staff.role == ROLE_SUPERVISOR, Staff.active,
                                                            Staff.email.is_not(None))).all() if e]


def _email(recipients: list[str], message: str, at, background: BackgroundTasks) -> bool:
    """Queue one email if email is set up and someone can receive it. Never blocks the request."""
    if not notify.email_enabled() or not recipients:
        return False
    background.add_task(notify.send_email, recipients, message, at)
    return True


def _get_request(db: Session, request_id: int):
    req = db.get(timeaway.TimeOffRequest, request_id)
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such time-off request.")
    return req


@router.get("/time-away")
def time_away(me: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """The Time away screen: my reports and requests, who's away in the next 14 days (US-37),
    and, for the supervisor and shift leads, requests to decide and recent sick/emergency reports."""
    return timeaway.screen(db, me, clock.utcnow())


@router.post("/absences", status_code=status.HTTP_201_CREATED)
def report_absence(body: AbsenceIn, background: BackgroundTasks, me: Staff = Depends(current_staff),
                   db: Session = Depends(get_db)):
    """US-34: tell the supervisor straight away that I can't make a shift."""
    now = clock.utcnow()
    try:
        report, message = timeaway.report_absence(db, me, body.kind, body.day, body.starts, body.ends, body.note, now)
    except timeaway.Refused as no:
        raise HTTPException(status.HTTP_409_CONFLICT if isinstance(no, timeaway.Clash) else 422, str(no))
    emailed = _email(_supervisor_emails(db), message, now, background)
    background.add_task(hub.broadcast, "timeaway")
    return {"id": report.id, "message": message, "late": report.late, "emailed": emailed,
            "reported_time": clock.fmt_time(now)}


@router.post("/time-off", status_code=status.HTTP_201_CREATED)
def request_time_off(body: TimeOffIn, background: BackgroundTasks, me: Staff = Depends(current_staff),
                     db: Session = Depends(get_db)):
    """US-35: ask for days off ahead of time. Starts as Pending."""
    now = clock.utcnow()
    try:
        req, message = timeaway.request_time_off(db, me, body.start, body.end, body.reason, now)
    except timeaway.Refused as no:
        raise HTTPException(status.HTTP_409_CONFLICT if isinstance(no, timeaway.Clash) else 422, str(no))
    emailed = _email(_supervisor_emails(db), message, now, background)
    background.add_task(hub.broadcast, "timeaway")
    return {"id": req.id, "status": req.status, "message": message, "emailed": emailed}


@router.post("/time-off/{request_id}/cancel")
def cancel_time_off(request_id: int, background: BackgroundTasks, me: Staff = Depends(current_staff),
                    db: Session = Depends(get_db)):
    """US-35 test 3: cancel my own request while it's still Pending."""
    now = clock.utcnow()
    req = _get_request(db, request_id)
    try:
        message = timeaway.cancel_time_off(db, me, req, now)
    except timeaway.Refused as no:
        raise HTTPException(status.HTTP_403_FORBIDDEN if req.staff_id != me.id else status.HTTP_409_CONFLICT, str(no))
    _email(_supervisor_emails(db), message, now, background)
    background.add_task(hub.broadcast, "timeaway")
    return {"id": req.id, "status": req.status}


@router.post("/time-off/{request_id}/decision")
def decide_time_off(request_id: int, body: DecisionIn, background: BackgroundTasks,
                    me: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-36: the supervisor or a shift lead approves or declines; the assistant is emailed the decision."""
    now = clock.utcnow()
    req = _get_request(db, request_id)
    try:
        message = timeaway.decide_time_off(db, me, req, body.approve, body.reason, now)
    except timeaway.Refused as no:
        code = status.HTTP_403_FORBIDDEN if not timeaway.is_senior(me) or req.staff_id == me.id else (
            status.HTTP_409_CONFLICT if req.status != timeaway.PENDING else 422)
        raise HTTPException(code, str(no))
    requester = req.staff.email
    emailed = _email([requester] if requester else [], message, now, background)
    background.add_task(hub.broadcast, "timeaway")
    return {"id": req.id, "status": req.status, "message": message, "emailed": emailed,
            "decided_by": me.display_name, "decided_time": clock.fmt_time(now)}
