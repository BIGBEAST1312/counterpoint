# Feature 2 · Ticket drafts & shift handover | Owner: Hetank Patel
# AI use: Used AI for concept explanations, understanding syntax, and general debugging guidance.
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.auth.deps import current_staff
from app.auth.models import Staff
from app.core import clock
from app.core.database import get_db
from app.core.realtime import hub

from .logic import summary_line, ticket_text
from .models import FOLLOW_UP_OUTCOMES, HandoverNote, TicketDraft
from .schemas import DraftIn, FollowUpIn, NoteIn, TdxIn

router = APIRouter(prefix="/api", tags=["Feature 2 · Ticket drafts & shift handover (Hetank)"])


def draft_out(d: TicketDraft) -> dict:
    return {"id": d.id, "author": d.author.display_name, "problem_type": d.problem_type,
            "reported": d.reported, "what_i_did": d.what_i_did, "outcome": d.outcome,
            "summary": summary_line(d), "text": ticket_text(d), "created_at": d.created_at,
            "tdx_number": d.tdx_number, "raised_at": d.raised_at, "locked": d.tdx_number is not None,
            "followed_up_at": d.followed_up_at, "follow_up_note": d.follow_up_note,
            "followed_up_by": d.followed_up_by.display_name if d.followed_up_by else None}


def note_out(n: HandoverNote) -> dict:
    return {"id": n.id, "text": n.text, "category": n.category, "urgent": n.urgent,
            "author": n.author.display_name, "created_at": n.created_at, "resolved_at": n.resolved_at,
            "resolved_by": n.resolved_by.display_name if n.resolved_by else None}


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
    if d.tdx_number:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"This draft is already raised as TeamDynamix {d.tdx_number}, so it's locked.")
    other = db.scalar(select(TicketDraft).where(TicketDraft.tdx_number == body.tdx_number, TicketDraft.id != d.id))
    if other:
        raise HTTPException(status.HTTP_409_CONFLICT, f"TeamDynamix number {body.tdx_number} is already used on another draft.")
    d.tdx_number, d.raised_at = body.tdx_number, clock.utcnow()
    db.commit()
    background.add_task(hub.broadcast, "tickets")
    return draft_out(d)


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


@router.get("/followups")
def followups(_: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-13: Escalated and Student returning drafts stay here until someone ticks them off."""
    q = (select(TicketDraft).where(TicketDraft.outcome.in_(FOLLOW_UP_OUTCOMES), TicketDraft.followed_up_at.is_(None))
         .order_by(TicketDraft.created_at))
    return [draft_out(d) for d in db.scalars(q).all()]


@router.post("/drafts/{draft_id}/followed-up")
def mark_followed_up(draft_id: int, body: FollowUpIn, background: BackgroundTasks, me: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    d = _get_draft(db, draft_id)
    if d.outcome not in FOLLOW_UP_OUTCOMES:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only Escalated or Student returning drafts need a follow-up.")
    if d.followed_up_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "This draft has already been followed up.")
    d.followed_up_at, d.followed_up_by_id, d.follow_up_note = clock.utcnow(), me.id, body.note.strip()
    db.commit()
    background.add_task(hub.broadcast, "tickets")
    return draft_out(d)


# ---------- E4 · Hand over the shift ----------

@router.post("/handover", status_code=status.HTTP_201_CREATED)
def write_note(body: NoteIn, background: BackgroundTasks, me: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-10."""
    n = HandoverNote(author_id=me.id, created_at=clock.utcnow(), **body.model_dump())
    db.add(n)
    db.commit()
    background.add_task(hub.broadcast, "handover")
    return note_out(n)


@router.get("/handover")
def open_notes(me: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-11: open notes, urgent first, then newest first. Also how many of my drafts
    are still unraised (US-09 test 3), so I'm reminded before I leave."""
    q = (select(HandoverNote).where(HandoverNote.resolved_at.is_(None))
         .order_by(case((HandoverNote.urgent, 0), else_=1), HandoverNote.created_at.desc()))
    my_unraised = db.scalar(select(func.count()).select_from(TicketDraft)
                            .where(TicketDraft.author_id == me.id, TicketDraft.tdx_number.is_(None))) or 0
    notes = [note_out(n) for n in db.scalars(q).all()]
    return {"notes": notes, "my_unraised_drafts": my_unraised,
            "message": None if notes else "Nothing handed over."}


@router.get("/handover/resolved")
def resolved_notes(_: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-12 test 2: resolved notes from the last 7 days stay readable."""
    from datetime import timedelta
    since = clock.utcnow() - timedelta(days=7)
    q = select(HandoverNote).where(HandoverNote.resolved_at >= since).order_by(HandoverNote.resolved_at.desc())
    return [note_out(n) for n in db.scalars(q).all()]


@router.patch("/handover/{note_id}/resolve")
def resolve_note(note_id: int, background: BackgroundTasks, me: Staff = Depends(current_staff), db: Session = Depends(get_db)):
    """US-12."""
    n = db.get(HandoverNote, note_id)
    if n is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such note.")
    if n.resolved_at:
        raise HTTPException(status.HTTP_409_CONFLICT, "That note is already resolved.")
    n.resolved_at, n.resolved_by_id = clock.utcnow(), me.id
    db.commit()
    background.add_task(hub.broadcast, "handover")
    return note_out(n)
