# Feature 1 (E1): request and reply shapes | Owner: Mohit Sawant
from pydantic import BaseModel, field_validator

from app.core.config import PROBLEM_TYPES

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
    place: int                      # 1 = next in line
    estimate_minutes: int | None
    message: str


class LeaveIn(BaseModel):
    ticket_no: int
    first_name: str
