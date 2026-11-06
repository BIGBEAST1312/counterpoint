# Feature 5 · Desk coverage · E11 Time away from the desk | Owner: Aarya Patel
# AI disclosure: with guidance of Claude (Anthropic).
"""Rules for sick and emergency reports (US-34), time-off requests (US-35), decisions (US-36)
and who's away in the next two weeks (US-37).

Each function returns the plain-English message to email, so the router only has to send it.
Privacy: whether a report was Sick or Emergency, its note, and time-off reasons are shown only to the
supervisor and shift leads (and to the person themselves). The team list shows names and dates only.
"""
import re
from datetime import date, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.auth.models import ROLE_LEAD, ROLE_SUPERVISOR, Staff
from app.core import clock

from .models import (ABSENCE_KINDS, APPROVED, CANCELLED, DECLINED, PENDING, AbsenceReport,  # noqa: F401
                     TimeOffRequest)

_HHMM = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
UPCOMING_DAYS = 14


class Refused(Exception):
    """A rule said no. The message is shown to the person as it is."""


class Clash(Refused):
    """Refused because it overlaps something already saved (sent back as 409 Conflict)."""


def is_senior(staff: Staff) -> bool:
    return staff.role in (ROLE_SUPERVISOR, ROLE_LEAD)


# ---------- wording ----------

def day_words(day: date, today: date) -> str:
    """'today', 'tomorrow' or 'Monday 2 November'."""
    if day == today:
        return "today"
    if day == today + timedelta(days=1):
        return "tomorrow"
    return f"{day.strftime('%A')} {day.day} {day.strftime('%B')}"


def date_range(start: date, end: date) -> str:
    """'2 November', '2–4 November' or '30 October – 2 November'."""
    if start == end:
        return f"{start.day} {start.strftime('%B')}"
    if (start.year, start.month) == (end.year, end.month):
        return f"{start.day}–{end.day} {end.strftime('%B')}"
    return f"{start.day} {start.strftime('%B')} – {end.day} {end.strftime('%B')}"


def shift_words(start: datetime, end: datetime, today: date) -> str:
    """'shift today 1:00–5:00 p.m.' (am/pm written once when both are the same)."""
    a, b = clock.fmt_time(start), clock.fmt_time(end)
    times = f"{a[:-5]}–{b}" if a[-4:] == b[-4:] else f"{a}–{b}"
    return f"shift {day_words(clock.local_date(start), today)} {times}"


# ---------- US-34 · Report sick or an emergency ----------

def report_absence(db: Session, me: Staff, kind: str, day: date, starts: str, ends: str, note: str,
                   now: datetime) -> tuple[AbsenceReport, str]:
    if kind not in ABSENCE_KINDS:
        raise Refused("Choose Sick or Emergency.")
    if not (_HHMM.match(starts or "") and _HHMM.match(ends or "")):
        raise Refused("Shift times must look like 13:00.")
    today = clock.local_date(now)
    if day < today:
        raise Refused("That shift has already passed.")
    start, end = clock.local_at(day, starts), clock.local_at(day, ends)
    if end <= start:
        raise Refused("The shift has to end after it starts.")
    note = (note or "").strip()
    if len(note) > 200:
        raise Refused("Keep the note to 200 characters.")
    clash = db.scalar(select(AbsenceReport).where(AbsenceReport.staff_id == me.id,
                                                  AbsenceReport.shift_start < end, AbsenceReport.shift_end > start))
    if clash:
        raise Clash("You've already reported this shift. The supervisor has been told.")
    report = AbsenceReport(staff_id=me.id, kind=kind, shift_start=start, shift_end=end, note=note,
                           reported_at=now, late=now > start)
    db.add(report)
    db.commit()
    verb = "reported sick" if kind == "sick" else "reported an emergency"
    message = f"{me.display_name} {verb} at {clock.fmt_time(now)} ({shift_words(start, end, today)})"
    if report.late:
        message += ", after the shift started"
    return report, message


# ---------- US-35 · Request time off ----------

def request_time_off(db: Session, me: Staff, start: date, end: date, reason: str,
                     now: datetime) -> tuple[TimeOffRequest, str]:
    today = clock.local_date(now)
    reason = (reason or "").strip()
    if start < today:
        raise Refused("The first day off can't be in the past.")
    if end < start:
        raise Refused("The last day off can't be before the first day.")
    if not reason:
        raise Refused("Add a short reason, such as \"Midterm week\".")
    if len(reason) > 120:
        raise Refused("Keep the reason to 120 characters.")
    clash = db.scalar(select(TimeOffRequest).where(TimeOffRequest.staff_id == me.id,
                                                   TimeOffRequest.status.in_((PENDING, APPROVED)),
                                                   TimeOffRequest.start_day <= end, TimeOffRequest.end_day >= start))
    if clash:
        raise Clash(f"You already have a {clash.status} request for {date_range(clash.start_day, clash.end_day)}. "
                    "Cancel it first, or pick other days.")
    req = TimeOffRequest(staff_id=me.id, start_day=start, end_day=end, reason=reason, status=PENDING,
                         requested_at=now)
    db.add(req)
    db.commit()
    return req, (f"{me.display_name} requested time off for {date_range(start, end)} "
                 f"(sent {clock.fmt_time(now)})")


def cancel_time_off(db: Session, me: Staff, req: TimeOffRequest, now: datetime) -> str:
    if req.staff_id != me.id:
        raise Refused("You can only cancel your own request.")
    if req.status != PENDING:
        raise Refused("This request has already been decided, so it can't be cancelled here. Talk to the supervisor.")
    req.status, req.decided_at = CANCELLED, now
    db.commit()
    return (f"{me.display_name} cancelled the time-off request for {date_range(req.start_day, req.end_day)} "
            f"at {clock.fmt_time(now)}")


# ---------- US-36 · Get a decision ----------

def decide_time_off(db: Session, me: Staff, req: TimeOffRequest, approve: bool, reason: str,
                    now: datetime) -> str:
    if not is_senior(me):
        raise Refused("Only the supervisor and shift leads decide time-off requests.")
    if req.staff_id == me.id:
        raise Refused("You can't decide your own request. Another shift lead or the supervisor has to.")
    if req.status != PENDING:
        raise Refused(f"This request is already {req.status}.")
    reason = (reason or "").strip()
    if not approve and not reason:
        raise Refused("Say why the request is declined. The assistant will see it.")
    if len(reason) > 200:
        raise Refused("Keep the reason to 200 characters.")
    req.status = APPROVED if approve else DECLINED
    req.decided_by_id, req.decided_at, req.decision_reason = me.id, now, reason
    db.commit()
    message = (f"Your time off for {date_range(req.start_day, req.end_day)} was "
               f"{'approved' if approve else 'declined'} at {clock.fmt_time(now)}")
    if reason:
        message += f" Reason: {reason}"
    return message


# ---------- US-37 · Who's away in the next two weeks, and the screen's data ----------

def upcoming(db: Session, now: datetime) -> list[dict]:
    """Each of the next 14 days with who is off. Names only: never the kind, reason or note."""
    today = clock.local_date(now)
    last = today + timedelta(days=UPCOMING_DAYS - 1)
    days = {today + timedelta(days=i): {} for i in range(UPCOMING_DAYS)}
    for r in db.scalars(select(AbsenceReport).where(AbsenceReport.shift_start >= clock.local_midnight_utc(today),
                                                    AbsenceReport.shift_start < clock.local_midnight_utc(last + timedelta(days=1)))):
        days[clock.local_date(r.shift_start)][r.staff_id] = r.staff.display_name
    for q in db.scalars(select(TimeOffRequest).where(TimeOffRequest.status == APPROVED,
                                                     and_(TimeOffRequest.start_day <= last,
                                                          TimeOffRequest.end_day >= today))):
        d = max(q.start_day, today)
        while d <= min(q.end_day, last):
            days[d][q.staff_id] = q.staff.display_name
            d += timedelta(days=1)
    return [{"date": d, "label": day_words(d, today), "weekday": d.strftime("%a"),
             "away": [{"staff_id": sid, "name": name} for sid, name in sorted(people.items(), key=lambda x: x[1])]}
            for d, people in days.items()]


def _request_out(q: TimeOffRequest) -> dict:
    return {"id": q.id, "name": q.staff.display_name, "staff_id": q.staff_id, "start": q.start_day, "end": q.end_day,
            "dates": date_range(q.start_day, q.end_day), "reason": q.reason, "status": q.status,
            "requested_at": q.requested_at, "requested_time": clock.fmt_time(q.requested_at),
            "decided_by": q.decided_by.display_name if q.decided_by else None, "decided_at": q.decided_at,
            "decided_time": clock.fmt_time(q.decided_at) if q.decided_at else None,
            "decision_reason": q.decision_reason}


def _report_out(r: AbsenceReport, today: date) -> dict:
    return {"id": r.id, "name": r.staff.display_name, "kind": r.kind, "kind_label": ABSENCE_KINDS[r.kind],
            "shift": shift_words(r.shift_start, r.shift_end, today), "note": r.note, "late": r.late,
            "reported_at": r.reported_at, "reported_time": clock.fmt_time(r.reported_at)}


def screen(db: Session, me: Staff, now: datetime) -> dict:
    """Everything the Time away screen shows to this person."""
    today = clock.local_date(now)
    senior = is_senior(me)
    mine = db.scalars(select(TimeOffRequest).where(TimeOffRequest.staff_id == me.id,
                                                   or_(TimeOffRequest.end_day >= today - timedelta(days=30),
                                                       TimeOffRequest.status == PENDING))
                      .order_by(TimeOffRequest.requested_at.desc())).all()
    since = clock.local_midnight_utc(today - timedelta(days=7))
    my_reports = db.scalars(select(AbsenceReport).where(AbsenceReport.staff_id == me.id, AbsenceReport.shift_start >= since)
                            .order_by(AbsenceReport.reported_at.desc())).all()
    out = {"senior": senior, "upcoming": upcoming(db, now),
           "my_requests": [_request_out(q) for q in mine],
           "my_reports": [_report_out(r, today) for r in my_reports]}
    if senior:
        pending = db.scalars(select(TimeOffRequest).where(TimeOffRequest.status == PENDING)
                             .order_by(TimeOffRequest.start_day)).all()
        out["to_decide"] = [dict(_request_out(q), own=q.staff_id == me.id) for q in pending]
        reports = db.scalars(select(AbsenceReport).where(AbsenceReport.shift_start >= since)
                             .order_by(AbsenceReport.reported_at.desc())).all()
        out["reports"] = [_report_out(r, today) for r in reports]
        out["decided"] = [_request_out(q) for q in db.scalars(
            select(TimeOffRequest).where(TimeOffRequest.status.in_((APPROVED, DECLINED)),
                                         TimeOffRequest.end_day >= today)
            .order_by(TimeOffRequest.start_day)).all()]
    return out
