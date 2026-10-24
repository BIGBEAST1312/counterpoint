# Feature 1 (E1): walk-up queue, check in and wait | Owner: Mohit Sawant
from datetime import date, datetime

from sqlalchemy import Date, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, UTCDateTime

# A visit's status: waiting -> called -> serving -> done, or waiting -> left, called -> gone
WAITING, CALLED, SERVING, DONE, LEFT, GONE = "waiting", "called", "serving", "done", "left", "gone"


class Visit(Base):
    """One student's place in the line. Only a first name is kept, never an NSID or student number."""

    __tablename__ = "visit"
    __table_args__ = (UniqueConstraint("ticket_date", "ticket_no"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_date: Mapped[date] = mapped_column(Date, index=True)   # numbers restart each day
    ticket_no: Mapped[int]
    first_name: Mapped[str] = mapped_column(String(40))
    problem_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(10), default=WAITING, index=True)
    counter: Mapped[str | None] = mapped_column(String(20), default=None)
    arrived_at: Mapped[datetime] = mapped_column(UTCDateTime)
    called_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    served_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    @property
    def ticket(self) -> str:
        return f"#{self.ticket_no:03d}"
