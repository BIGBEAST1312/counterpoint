# Feature 2 · Ticket drafts & shift handover | Owner: Hetank Patel
# AI use: Used AI for concept explanations, understanding syntax, and general debugging guidance.
# Product v1 (Deliverable 2): E3 · Write tickets while they're fresh (US-07 to US-09).
# E4 · Hand over the shift (US-10 to US-13) comes in Product v2.
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.deps import current_staff
from app.auth.models import Staff
from app.core import clock
from app.core.database import get_db
from app.core.realtime import hub

from .logic import summary_line, ticket_text
from .models import TicketDraft
from .schemas import DraftIn, TdxIn

router = APIRouter(prefix="/api", tags=["Feature 2 · Ticket drafts & shift handover (Hetank)"])


def draft_out(d: TicketDraft) -> dict:
    return {"id": d.id, "author": d.author.display_name, "problem_type": d.problem_type,
            "reported": d.reported, "what_i_did": d.what_i_did, "outcome": d.outcome,
            "summary": summary_line(d), "text": ticket_text(d), "created_at": d.created_at,
            "tdx_number": d.tdx_number, "raised_at": d.raised_at, "locked": d.tdx_number is not None}


def _get_draft(db, draft_id) -> TicketDraft:
    d = db.get(TicketDraft, draft_id)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such draft.")
    return d


# ---------- E3 · Write tickets while they're fresh ----------

@router.post("/drafts", status_code=status.HTTP_201_CREATED)
def make_draft(body: DraftIn, background: BackgroundTasks, me: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-07: ticket text ready to paste into TeamDynamix."""
    d = TicketDraft(author_id=me.id, created_at=clock.utcnow(), **body.model_dump())
    db.add(d)
    db.commit()
    background.add_task(hub.broadcast, "tickets")
    return draft_out(d)


@router.put("/drafts/{draft_id}")
def edit_draft(draft_id: int, body: DraftIn, background: BackgroundTasks, _: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-07 test 4: a draft can be fixed until its TeamDynamix number is recorded."""
    d = _get_draft(db, draft_id)
    if d.tdx_number:
        raise HTTPException(status.HTTP_409_CONFLICT, "This draft has been raised in TeamDynamix, so it's locked.")
    for k, v in body.model_dump().items():
        setattr(d, k, v)
    db.commit()
    background.add_task(hub.broadcast, "tickets")
    return draft_out(d)


@router.patch("/drafts/{draft_id}/tdx")
def record_tdx(draft_id: int, body: TdxIn, background: BackgroundTasks, _: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-08: mark the draft Raised with its TeamDynamix number."""
    d = _get_draft(db, draft_id)
    other = db.scalar(select(TicketDraft).where(TicketDraft.tdx_number == body.tdx_number, TicketDraft.id != d.id))
    if other:
        raise HTTPException(status.HTTP_409_CONFLICT, f"TeamDynamix number {body.tdx_number} is already used on another draft.")
    d.tdx_number, d.raised_at = body.tdx_number, clock.utcnow()
    db.commit()
    background.add_task(hub.broadcast, "tickets")
    return draft_out(d)


@router.get("/drafts/reminder")
def unraised_reminder(me: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-09 test 3: how many of my drafts still need a TeamDynamix number, so I'm reminded before I leave.
    (In Product v2 the handover screen shows this too.)"""
    n = db.scalar(select(func.count()).select_from(TicketDraft)
                  .where(TicketDraft.author_id == me.id, TicketDraft.tdx_number.is_(None))) or 0
    return {"my_unraised_drafts": n,
            "message": None if not n else f"You still have {n} draft{'' if n == 1 else 's'} to raise in TeamDynamix."}


@router.get("/drafts")
def list_drafts(raised: bool | None = None, mine: bool = False, me: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-09: `?raised=false` lists drafts without a TeamDynamix number, oldest first."""
    q = select(TicketDraft)
    if raised is False:
        q = q.where(TicketDraft.tdx_number.is_(None)).order_by(TicketDraft.created_at)
    else:
        if raised:
            q = q.where(TicketDraft.tdx_number.is_not(None))
        q = q.order_by(TicketDraft.created_at.desc())
    if mine:
        q = q.where(TicketDraft.author_id == me.id)
    return [draft_out(d) for d in db.scalars(q.limit(200)).all()]
