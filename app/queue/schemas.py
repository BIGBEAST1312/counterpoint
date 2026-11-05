# Feature 1 · Walk-up queue | Owner: Mohit Sawant
# AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the owner.
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.core.config import COUNTERS, PROBLEM_TYPES

from .logic import check_first_name


class CheckIn(BaseModel):
    first_name: str = ""
    problem_type: str = ""

    @field_validator("first_name")
    @classmethod
    def first_name_only(cls, v: str) -> str:
        return check_first_name(v)

    @field_validator("problem_type")
    @classmethod
    def known_type(cls, v: str) -> str:
        if v not in PROBLEM_TYPES:
            raise ValueError("Please pick what you need help with.")
        return v


class CheckInOut(BaseModel):
    ticket: str
    place: int            # 1 = next to be called
    estimate_minutes: int | None
    message: str


class LeaveIn(BaseModel):
    ticket_no: int
    first_name: str


class CallIn(BaseModel):
    counter: str

    @field_validator("counter")
    @classmethod
    def real_counter(cls, v: str) -> str:
        if v not in COUNTERS:
            raise ValueError(f"Unknown counter. The desk has {' and '.join(COUNTERS)}.")
        return v


class VisitOut(BaseModel):
    """Staff view of a place in line (signed-in screens only)."""
    id: int
    ticket: str
    first_name: str
    problem_type: str
    status: str
    counter: str | None
    arrived_at: datetime
    called_at: datetime | None


class LobbyCall(BaseModel):
    """Public lobby screen: ticket and counter only, never a name or problem type (US-05)."""
    ticket: str
    counter: str | None
    missed: bool
