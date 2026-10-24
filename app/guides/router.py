# Feature 3 · Fix guides | Owner: Priyesh Patel
# # AI disclosure: Used AI for concept explanations, understanding syntax and debugging guidance.
# Product v1 (Deliverable 2): E5 · Find the right fix fast (US-14 to US-16).
# E6 · Keep guides trustworthy (US-17 write/edit, US-18 flag, US-19 review) comes in Product v2.
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import current_staff
from app.auth.models import Staff
from app.core import clock
from app.core.config import PROBLEM_TYPES
from app.core.database import get_db

from .logic import search_score
from .models import Guide

router = APIRouter(prefix="/api/guides", tags=["Feature 3 · Fix guides (Priyesh)"])


def summary(g: Guide, now) -> dict:
    flag = g.open_flag
    return {"id": g.id, "title": g.title, "problem_type": g.problem_type,
            "problem_label": PROBLEM_TYPES.get(g.problem_type, g.problem_type),
            "reviewed_at": g.reviewed_at, "flagged": flag is not None,   # US-14 test 3
            "step_count": len(g.steps)}


def full(g: Guide, now) -> dict:
    flag = g.open_flag
    return {**summary(g, now), "before_you_start": g.before_you_start,
            "steps": [s.text for s in g.steps],
            "created_by": g.created_by.display_name, "created_at": g.created_at,
            "edited_by": g.edited_by.display_name if g.edited_by else None, "edited_at": g.edited_at,
            "reviewed_by": g.reviewed_by.display_name if g.reviewed_by else None,
            "flag": None if flag is None else {"id": flag.id, "reason": flag.reason,
                                               "by": flag.flagged_by.display_name, "at": flag.flagged_at}}


def _get(db, guide_id) -> Guide:
    g = db.get(Guide, guide_id)
    if g is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such guide.")
    return g


# ---------- E5 · Find the right fix fast ----------

@router.get("")
def browse(problem_type: str = Query(...), _: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-14: guides for one problem type, alphabetical."""
    if problem_type not in PROBLEM_TYPES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown problem type.")
    now = clock.utcnow()
    guides = db.scalars(select(Guide).where(Guide.problem_type == problem_type)).all()
    rows = sorted((summary(g, now) for g in guides), key=lambda r: r["title"].lower())
    return {"guides": rows, "message": None if rows else "No guides for this yet."}


@router.get("/search")
def search(q: str = Query("", max_length=100), _: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-15: keyword search, title matches first."""
    now = clock.utcnow()
    scored = [(search_score(g, q), g) for g in db.scalars(select(Guide)).all()]
    hits = [summary(g, now) for s, g in sorted(scored, key=lambda t: (-t[0], t[1].title.lower())) if s > 0]
    return {"guides": hits,
            "message": None if hits else "No guides found. Try browsing by problem type instead."}


@router.get("/{guide_id}")
def open_guide(guide_id: int, _: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-16: the guide as numbered steps (ticking them off happens in the browser)."""
    return full(_get(db, guide_id), clock.utcnow())
