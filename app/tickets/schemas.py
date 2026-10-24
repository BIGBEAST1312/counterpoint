# Feature 2 · Ticket drafts & shift handover | Owner: Hetank Patel
# AI use: Used AI for concept explanations, understanding syntax, and general debugging guidance.
from pydantic import BaseModel, Field, field_validator

from app.core.config import PROBLEM_TYPES

from .models import OUTCOMES


class DraftIn(BaseModel):
    problem_type: str
    reported: str = Field(max_length=2000)
    what_i_did: str = Field(default="", max_length=2000)
    outcome: str = ""

    @field_validator("problem_type")
    @classmethod
    def known_type(cls, v):
        if v not in PROBLEM_TYPES:
            raise ValueError("Pick a problem type.")
        return v

    @field_validator("reported")
    @classmethod
    def has_report(cls, v):
        if not v.strip():
            raise ValueError("Say what the student reported.")
        return v

    @field_validator("what_i_did")
    @classmethod
    def has_work(cls, v):
        if not v.strip():
            raise ValueError("Fill in \"What I did\".")
        return v

    @field_validator("outcome")
    @classmethod
    def known_outcome(cls, v):
        if v not in OUTCOMES:
            raise ValueError("Pick an outcome: Solved, Escalated or Student returning.")
        return v


class TdxIn(BaseModel):
    tdx_number: str

    @field_validator("tdx_number")
    @classmethod
    def digits_only(cls, v):
        v = v.strip()
        if not v.isdigit():
            raise ValueError("TeamDynamix numbers are digits only.")
        return v
