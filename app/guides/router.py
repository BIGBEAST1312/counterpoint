# Feature 3 · Fix guides | Owner: Priyesh Patel
# # AI disclosure: Used AI for concept explanations, understanding syntax and debugging guidance.
# Product v1 (Deliverable 2): E5 · Find the right fix fast (US-14 to US-16).
# E6 · Keep guides trustworthy (US-17 write/edit, US-18 flag, US-19 review) comes in Product v2.
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import current_staff, senior_only
from app.auth.models import Staff
from app.core import clock
from app.core.config import PROBLEM_TYPES
from app.core.database import get_db
from app.core.realtime import hub

from .logic import needs_review, search_score
from .models import Guide, GuideFlag, GuideStep
from .schemas import FlagIn, GuideIn

router = APIRouter(prefix="/api/guides", tags=["Feature 3 · Fix guides (Priyesh)"])


def summary(g: Guide, now) -> dict:
    flag = g.open_flag
    return {"id": g.id, "title": g.title, "problem_type": g.problem_type,
            "problem_label": PROBLEM_TYPES.get(g.problem_type, g.problem_type),
            "reviewed_at": g.reviewed_at, "needs_review": needs_review(g, now),
            "flagged": flag is not None, "step_count": len(g.steps)}


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


@router.get("/needs-fixing")
def needs_fixing(_: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-18 test 4: flagged guides, oldest flag first."""
    now = clock.utcnow()
    flags = db.scalars(select(GuideFlag).where(GuideFlag.fixed_at.is_(None)).order_by(GuideFlag.flagged_at)).all()
    return [{**summary(db.get(Guide, f.guide_id), now), "reason": f.reason, "flagged_at": f.flagged_at,
             "flagged_by": f.flagged_by.display_name} for f in flags]


@router.get("/{guide_id}")
def open_guide(guide_id: int, _: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-16: the guide as numbered steps (ticking them off happens in the browser)."""
    return full(_get(db, guide_id), clock.utcnow())


# ---------- E6 · Keep guides trustworthy ----------

def _set_steps(g: Guide, steps: list[str]) -> None:
    g.steps.clear()
    for i, text in enumerate(steps, start=1):
        g.steps.append(GuideStep(position=i, text=text))


@router.post("", status_code=status.HTTP_201_CREATED)
def create(body: GuideIn, background: BackgroundTasks, me: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-17 test 1."""
    now = clock.utcnow()
    g = Guide(title=body.title, problem_type=body.problem_type, before_you_start=body.before_you_start.strip(),
              created_by_id=me.id, created_at=now, reviewed_at=now)
    _set_steps(g, body.steps)
    db.add(g)
    db.commit()
    background.add_task(hub.broadcast, "guides")
    return full(g, now)


@router.put("/{guide_id}")
def edit(guide_id: int, body: GuideIn, background: BackgroundTasks, me: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-17 tests 3-4: edit text, add, remove or reorder steps (send them in the new order)."""
    g = _get(db, guide_id)
    now = clock.utcnow()
    g.title, g.problem_type, g.before_you_start = body.title, body.problem_type, body.before_you_start.strip()
    _set_steps(g, body.steps)
    g.edited_by_id, g.edited_at = me.id, now
    db.commit()
    db.refresh(g)
    background.add_task(hub.broadcast, "guides")
    return full(g, now)


@router.post("/{guide_id}/flag")
def flag(guide_id: int, body: FlagIn, background: BackgroundTasks, me: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-18 test 1."""
    g = _get(db, guide_id)
    if g.open_flag:
        raise HTTPException(status.HTTP_409_CONFLICT, "This guide is already flagged.")
    g.flags.append(GuideFlag(reason=body.reason, flagged_by_id=me.id, flagged_at=clock.utcnow()))
    db.commit()
    db.refresh(g)
    background.add_task(hub.broadcast, "guides")
    return full(g, clock.utcnow())


@router.post("/{guide_id}/flag/fixed")
def fix_flag(guide_id: int, background: BackgroundTasks, me: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-18 test 3."""
    g = _get(db, guide_id)
    f = g.open_flag
    if f is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "This guide isn't flagged.")
    f.fixed_at, f.fixed_by_id = clock.utcnow(), me.id
    db.commit()
    db.refresh(g)
    background.add_task(hub.broadcast, "guides")
    return full(g, clock.utcnow())


@router.post("/{guide_id}/reviewed")
def mark_reviewed(guide_id: int, background: BackgroundTasks, me: Staff = Depends(senior_only), db: Session = Depends(get_db)):
    """US-19 test 2: a senior assistant confirms the guide still works."""
    g = _get(db, guide_id)
    now = clock.utcnow()
    g.reviewed_at, g.reviewed_by_id = now, me.id
    db.commit()
    background.add_task(hub.broadcast, "guides")
    return full(g, now)
