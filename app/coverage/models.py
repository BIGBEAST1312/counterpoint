# Feature 5 · Desk coverage | Owner: Aarya Patel
# AI disclosure: with guidance of Claude (Anthropic).
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.models import Staff
from app.core.database import Base, UTCDateTime

ON_DESK, ON_BREAK, AT_LUNCH, STEPPED_AWAY, OFF_SHIFT = "on_desk", "on_break", "at_lunch", "stepped_away", "off_shift"
LABELS = {ON_DESK: "On desk", ON_BREAK: "On break", AT_LUNCH: "At lunch",
          STEPPED_AWAY: "Stepped away", OFF_SHIFT: "Off shift"}
AWAY = (ON_BREAK, AT_LUNCH, STEPPED_AWAY)


class StaffStatus(Base):
    """Where each staff member is right now (US-26). Replaces the Teams check-in chat."""

    __tablename__ = "staff_status"

    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(14), default=OFF_SHIFT)
    since: Mapped[datetime] = mapped_column(UTCDateTime)
    back_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    on_desk_stretch_from: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)  # US-29

    staff: Mapped[Staff] = relationship()


class StatusEvent(Base):
    """Every status change, with its time. Used for 'unattended since' and the supervisor feed."""

    __tablename__ = "status_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id"), index=True)
    from_status: Mapped[str] = mapped_column(String(14))
    to_status: Mapped[str] = mapped_column(String(14))
    at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    back_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)


class SupervisorNotification(Base):
    """US-33: one notification per status change, kept for the supervisor's feed."""

    __tablename__ = "supervisor_notification"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("status_event.id"))
    staff_name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(20))       # checked_in, checked_out, on_break, at_lunch, stepped_away, back
    message: Mapped[str] = mapped_column(String(200))   # e.g. "Sam went on break at 2:05 p.m."
    at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    read_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    emailed: Mapped[bool] = mapped_column(default=False)


class DeskHours(Base):
    """US-32: opening hours for each weekday (0 = Monday). opens = None means closed all day."""

    __tablename__ = "desk_hours"

    weekday: Mapped[int] = mapped_column(primary_key=True)
    opens: Mapped[str | None] = mapped_column(String(5), default=None)   # "09:30"
    closes: Mapped[str | None] = mapped_column(String(5), default=None)  # "21:00"


class ClosedDay(Base):
    """US-32 test 2: a day the desk is closed, e.g. a university holiday."""

    __tablename__ = "closed_day"

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    reason: Mapped[str] = mapped_column(String(80), default="")


# ---------- E11 · Time away from the desk (Deliverable 3) ----------

SICK, EMERGENCY = "sick", "emergency"
ABSENCE_KINDS = {SICK: "Sick", EMERGENCY: "Emergency"}
PENDING, APPROVED, DECLINED, CANCELLED = "pending", "approved", "declined", "cancelled"


class AbsenceReport(Base):
    """US-34: 'I can't make my shift', sent the moment it happens. No medical details are asked for."""

    __tablename__ = "absence_report"

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id"), index=True)
    kind: Mapped[str] = mapped_column(String(10))                 # sick or emergency (supervisor and leads only)
    shift_start: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    shift_end: Mapped[datetime] = mapped_column(UTCDateTime)
    note: Mapped[str] = mapped_column(String(200), default="")    # optional; supervisor and leads only
    reported_at: Mapped[datetime] = mapped_column(UTCDateTime)
    late: Mapped[bool] = mapped_column(default=False)             # reported after the shift started

    staff: Mapped[Staff] = relationship()


class TimeOffRequest(Base):
    """US-35, US-36: days off asked for ahead of time, decided by the supervisor or a shift lead."""

    __tablename__ = "time_off_request"

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id"), index=True)
    start_day: Mapped[date] = mapped_column(Date, index=True)
    end_day: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(10), default=PENDING)
    requested_at: Mapped[datetime] = mapped_column(UTCDateTime)
    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id"), default=None)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    decision_reason: Mapped[str] = mapped_column(String(200), default="")

    staff: Mapped[Staff] = relationship(foreign_keys=[staff_id])
    decided_by: Mapped[Staff | None] = relationship(foreign_keys=[decided_by_id])
