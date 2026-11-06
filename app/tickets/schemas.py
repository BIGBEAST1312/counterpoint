# Feature 2 · Ticket drafts & shift handover | Owner: Hetank Patel
# AI use: Used AI for concept explanations, understanding syntax, and general debugging guidance.
from pydantic import BaseModel, Field, field_validator

from app.core.config import PROBLEM_TYPES

from .models import CATEGORIES, OUTCOMES


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


class FollowUpIn(BaseModel):
    note: str = Field(max_length=500)

    @field_validator("note")
    @classmethod
    def has_note(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Add a short note saying what you did.")
        return v


class NoteIn(BaseModel):
    text: str = ""
    category: str = "FYI"
    urgent: bool = False

    @field_validator("text")
    @classmethod
    def length(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Write something in the note.")
        if len(v) > 500:
            raise ValueError("Notes can be 500 characters at most.")
        return v

    @field_validator("category")
    @classmethod
    def known_category(cls, v):
        if v not in CATEGORIES:
            raise ValueError("Category must be Follow-up, Equipment or FYI.")
        return v
