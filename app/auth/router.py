# Shared infrastructure: staff sign-in | Built by Hetank Patel, owned by no feature
# AI use: Used AI for concept explanations, understanding syntax, and general debugging guidance.

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import COUNTERS, PROBLEM_TYPES, SESSION_HOURS
from app.core.database import get_db

from .deps import bearer_token, current_staff, supervisor_only
from .models import LoginSession, Staff
from .schemas import LoginIn, LoginOut, StaffCreate, StaffOut
from .security import hash_password, new_token, token_hash, verify_password

router = APIRouter(prefix="/api", tags=["Shared · Sign-in & settings"])


@router.post("/auth/login", response_model=LoginOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    staff = db.scalar(select(Staff).where(Staff.username == body.username.strip().lower()))
    # Same message for "no such user" and "wrong password" so the form doesn't reveal usernames.
    if staff is None or not staff.active or not verify_password(body.password, staff.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong username or password.")
    token = new_token()
    db.add(LoginSession(token_hash=token_hash(token), staff_id=staff.id,
                        expires_at=clock.utcnow() + timedelta(hours=SESSION_HOURS)))
    db.commit()
    return LoginOut(token=token, staff=StaffOut.model_validate(staff))


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: str | None = Depends(bearer_token), db: Session = Depends(get_db)):
    if token:
        db.execute(delete(LoginSession).where(LoginSession.token_hash == token_hash(token)))
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/auth/me", response_model=StaffOut)
def me(staff: Staff = Depends(current_staff)):
    return staff


@router.post("/staff", response_model=StaffOut, status_code=status.HTTP_201_CREATED)
def create_staff(body: StaffCreate, _: Staff = Depends(supervisor_only), db: Session = Depends(get_db)):
    username = body.username.lower()
    if db.scalar(select(Staff).where(Staff.username == username)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"The username {username!r} is taken.")
    staff = Staff(username=username, display_name=body.display_name.strip(), email=body.email,
                  password_hash=hash_password(body.password), role=body.role)
    db.add(staff)
    db.commit()
    return staff


@router.get("/settings")
def settings():
    """Fixed lists every screen needs. Public: contains no personal data."""
    return {"counters": COUNTERS,
            "problem_types": [{"key": k, "label": v} for k, v in PROBLEM_TYPES.items()]}
