# Shared infrastructure: staff sign-in | Built by Hetank Patel, owned by no feature
# AI use: Used AI for concept explanations, understanding syntax, and general debugging guidance.
"""Route guards every feature uses:

    from app.auth.deps import current_staff
    @router.get("/thing")
    def thing(me: Staff = Depends(current_staff)): ...
"""
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core import clock
from app.core.database import get_db

from .models import ROLE_LEAD, ROLE_SUPERVISOR, LoginSession, Staff
from .security import token_hash


def bearer_token(authorization: str | None = Header(default=None)) -> str | None:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip() or None
    return None


def current_staff(token: str | None = Depends(bearer_token), db: Session = Depends(get_db)) -> Staff:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sign in to use the staff screens.")
    session = db.get(LoginSession, token_hash(token))
    if session is None or session.expires_at < clock.utcnow() or not session.staff.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Your sign-in has expired. Sign in again.")
    return session.staff


def senior_only(me: Staff = Depends(current_staff)) -> Staff:
    """Shift leads and the supervisor."""
    if me.role not in (ROLE_LEAD, ROLE_SUPERVISOR):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a shift lead or the supervisor can do this.")
    return me


def supervisor_only(me: Staff = Depends(current_staff)) -> Staff:
    if me.role != ROLE_SUPERVISOR:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the desk supervisor can do this.")
    return me
