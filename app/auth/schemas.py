# Shared infrastructure: staff sign-in | Built by Hetank Patel, owned by no feature
# AI use: Used AI for concept explanations, understanding syntax, and general debugging guidance.
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import ROLES


class StaffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    display_name: str
    role: str


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=40)
    password: str = Field(min_length=1, max_length=200)


class LoginOut(BaseModel):
    token: str
    staff: StaffOut


class StaffCreate(BaseModel):
    username: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9._-]+$")
    display_name: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=8, max_length=200)
    role: str = "assistant"
    email: str | None = Field(default=None, max_length=120)

    @field_validator("role")
    @classmethod
    def known_role(cls, v: str) -> str:
        if v not in ROLES:
            raise ValueError(f"Role must be one of: {', '.join(ROLES)}")
        return v
