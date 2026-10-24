# Feature 5 · Desk coverage | Owner: Aarya Patel
# AI disclosure: with guidance of Claude (Anthropic).
from datetime import datetime

from sqlalchemy import ForeignKey, String
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
