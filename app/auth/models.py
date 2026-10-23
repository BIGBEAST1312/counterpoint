# Shared infrastructure: staff sign-in | Built by Hetank Patel, owned by no feature
# AI use: Used AI for concept explanations, understanding syntax, and general debugging guidance.
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, UTCDateTime

ROLE_ASSISTANT = "assistant"    # student assistant
ROLE_LEAD = "lead"              # shift lead / senior assistant: can review guides, edit desk hours
ROLE_SUPERVISOR = "supervisor"  # desk supervisor: receives status notifications, can add staff
ROLES = (ROLE_ASSISTANT, ROLE_LEAD, ROLE_SUPERVISOR)


class Staff(Base):
    """A person who signs in to the staff screens. Students never have accounts."""

    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(12), default=ROLE_ASSISTANT)
    email: Mapped[str | None] = mapped_column(String(120), default=None)  # used only for supervisor emails
    active: Mapped[bool] = mapped_column(default=True)


class LoginSession(Base):
    """One row per signed-in browser. We store a hash of the token, never the token itself,
    so a leaked database can't be used to sign in."""

    __tablename__ = "login_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)

    staff: Mapped[Staff] = relationship()
