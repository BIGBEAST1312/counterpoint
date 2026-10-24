# Feature 2 · Ticket drafts & shift handover | Owner: Hetank Patel
# AI use: Used AI for concept explanations, understanding syntax, and general debugging guidance.
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.models import Staff
from app.core.database import Base, UTCDateTime

OUTCOMES = ("Solved", "Escalated", "Student returning")   # US-07 test 3
FOLLOW_UP_OUTCOMES = ("Escalated", "Student returning")     # US-13
CATEGORIES = ("Follow-up", "Equipment", "FYI")              # US-10 test 2


class TicketDraft(Base):
    """Ticket text an assistant writes right after helping a student (US-07).
    Written per student helped; it does not read the walk-up queue."""

    __tablename__ = "ticket_draft"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("staff.id"), index=True)
    problem_type: Mapped[str] = mapped_column(String(20))
    reported: Mapped[str] = mapped_column(Text)        # what the student reported
    what_i_did: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    tdx_number: Mapped[str | None] = mapped_column(String(20), unique=True, default=None)  # US-08
    raised_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    followed_up_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)       # US-13
    followed_up_by_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id"), default=None)
    follow_up_note: Mapped[str | None] = mapped_column(Text, default=None)

    author: Mapped[Staff] = relationship(foreign_keys=[author_id])
    followed_up_by: Mapped[Staff | None] = relationship(foreign_keys=[followed_up_by_id])


class HandoverNote(Base):
    """A note for the next shift (US-10 to US-12)."""

    __tablename__ = "handover_note"

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("staff.id"))
    text: Mapped[str] = mapped_column(String(500))
    category: Mapped[str] = mapped_column(String(12))
    urgent: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    resolved_by_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id"), default=None)

    author: Mapped[Staff] = relationship(foreign_keys=[author_id])
    resolved_by: Mapped[Staff | None] = relationship(foreign_keys=[resolved_by_id])
