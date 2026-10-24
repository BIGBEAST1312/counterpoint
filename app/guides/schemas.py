# Feature 3 · Fix guides | Owner: Priyesh Patel
# # AI disclosure: Used AI for concept explanations, understanding syntax and debugging guidance.
from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.config import GUIDE_MAX_STEPS, PROBLEM_TYPES


class GuideIn(BaseModel):
    title: str = ""
    problem_type: str
    before_you_start: str = Field(default="", max_length=1000)
    steps: list[str] = []

    @field_validator("problem_type")
    @classmethod
    def known_type(cls, v):
        if v not in PROBLEM_TYPES:
            raise ValueError("Pick a problem type.")
        return v

    @model_validator(mode="after")
    def limits(self):
        """US-17 test 2."""
        self.title = self.title.strip()
        self.steps = [s.strip() for s in self.steps if s.strip()]
        if not self.title:
            raise ValueError("Give the guide a title.")
        if len(self.title) > 120:
            raise ValueError("Keep the title under 120 characters.")
        if not self.steps:
            raise ValueError("Add at least one step.")
        if len(self.steps) > GUIDE_MAX_STEPS:
            raise ValueError(f"Guides can have {GUIDE_MAX_STEPS} steps at most. Split it into two guides.")
        return self


class FlagIn(BaseModel):
    reason: str = ""

    @field_validator("reason")
    @classmethod
    def has_reason(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Say what's wrong so it can be fixed.")
        return v[:300]
