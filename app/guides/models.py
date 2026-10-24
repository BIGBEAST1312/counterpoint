# Feature 3 · Fix guides | Owner: Priyesh Patel
# AI disclosure: Used AI for concept explanations, understanding syntax and debugging guidance.
from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.auth.models import Staff
from app.core.database import Base, UTCDateTime


class Guide(Base):
    """A step-by-step fix for one kind of problem (US-14 to US-19)."""

    __tablename__ = "guide"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    problem_type: Mapped[str] = mapped_column(String(20), index=True)
    before_you_start: Mapped[str] = mapped_column(Text, default="")   # US-16 test 4
    created_by_id: Mapped[int] = mapped_column(ForeignKey("staff.id"))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    edited_by_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id"), default=None)
    edited_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id"), default=None)
    reviewed_at: Mapped[datetime] = mapped_column(UTCDateTime)          # starts as the creation time

    steps: Mapped[list["GuideStep"]] = relationship(order_by="GuideStep.position", cascade="all, delete-orphan")
    flags: Mapped[list["GuideFlag"]] = relationship(order_by="GuideFlag.flagged_at", cascade="all, delete-orphan")
    created_by: Mapped[Staff] = relationship(foreign_keys=[created_by_id])
    edited_by: Mapped[Staff | None] = relationship(foreign_keys=[edited_by_id])
    reviewed_by: Mapped[Staff | None] = relationship(foreign_keys=[reviewed_by_id])

    @property
    def open_flag(self) -> "GuideFlag | None":
        return next((f for f in self.flags if f.fixed_at is None), None)


class GuideStep(Base):
    __tablename__ = "guide_step"

    id: Mapped[int] = mapped_column(primary_key=True)
    guide_id: Mapped[int] = mapped_column(ForeignKey("guide.id"), index=True)
    position: Mapped[int]
    text: Mapped[str] = mapped_column(Text)


class GuideFlag(Base):
    """US-18: someone found the guide's steps no longer work."""

    __tablename__ = "guide_flag"

    id: Mapped[int] = mapped_column(primary_key=True)
    guide_id: Mapped[int] = mapped_column(ForeignKey("guide.id"), index=True)
    reason: Mapped[str] = mapped_column(String(300))
    flagged_by_id: Mapped[int] = mapped_column(ForeignKey("staff.id"))
    flagged_at: Mapped[datetime] = mapped_column(UTCDateTime)
    fixed_by_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id"), default=None)
    fixed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, default=None)

    flagged_by: Mapped[Staff] = relationship(foreign_keys=[flagged_by_id])
