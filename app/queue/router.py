# Feature 1 · Walk-up queue | Owner: Mohit Sawant
# AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the owner.
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import current_staff
from app.core import clock
from app.core.database import get_db
from app.core.realtime import hub

from . import logic
from .models import CALLED, DONE, GONE, LEFT, SERVING, WAITING, Visit
from .schemas import CallIn, CheckIn, CheckInOut, LeaveIn, LobbyCall, VisitOut

router = APIRouter(prefix="/api", tags=["Feature 1 · Walk-up queue (Mohit)"])


def _estimate_for(db, ahead: int, now) -> int | None:
    return logic.estimate_minutes(ahead, logic.service_rate(db, now), logic.counters_calling(db, now))


def _wait_text(est: int | None) -> str:
    if est is None:
        return "The wait can't be estimated right now. You still have your place in line."
    if est == 0:
        return "You're next."
    return f"About {est} minutes."


def _to_out(v: Visit) -> VisitOut:
    return VisitOut(id=v.id, ticket=v.ticket, first_name=v.first_name, problem_type=v.problem_type,
                    status=v.status, counter=v.counter, arrived_at=v.arrived_at, called_at=v.called_at)


# ---------- Student side (kiosk and lobby: no sign-in) ----------

@router.post("/visits", response_model=CheckInOut, status_code=status.HTTP_201_CREATED)
def check_in(body: CheckIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    """US-01 + US-02: get a ticket number, a place in line and an estimated wait."""
    now = clock.utcnow()
    logic.sweep_missed(db, now)
    for _ in range(3):  # two kiosks at the same instant could pick the same number; retry
        visit = Visit(ticket_date=clock.local_date(now), ticket_no=logic.next_ticket_no(db, now),
                      first_name=body.first_name, problem_type=body.problem_type, arrived_at=now)
        db.add(visit)
        try:
            db.commit()
            break
        except IntegrityError:
            db.rollback()
    else:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Please try again.")
    ahead = len(logic.waiting_line(db)) - 1
    est = _estimate_for(db, ahead, now)
    background.add_task(hub.broadcast, "queue")
    return CheckInOut(ticket=visit.ticket, place=ahead + 1, estimate_minutes=est, message=_wait_text(est))


@router.get("/visits/place")
def my_place(ticket_no: int = Query(ge=1), db: Session = Depends(get_db)):
    """Check my place (US-04 test 4). Returns only a position and estimate, nothing personal."""
    now = clock.utcnow()
    logic.sweep_missed(db, now)
    visit = db.scalar(select(Visit).where(Visit.ticket_date == clock.local_date(now), Visit.ticket_no == ticket_no))
    if visit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That ticket wasn't found today.")
    if visit.status != WAITING:
        return {"ticket": visit.ticket, "status": visit.status, "place": None, "counter": visit.counter}
    line = logic.waiting_line(db)
    ahead = next(i for i, v in enumerate(line) if v.id == visit.id)
    est = _estimate_for(db, ahead, now)
    return {"ticket": visit.ticket, "status": WAITING, "place": ahead + 1, "estimate_minutes": est,
            "message": _wait_text(est)}


@router.post("/visits/leave")
def leave_line(body: LeaveIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    """US-03: a student takes themselves out of the line with their ticket number and first name."""
    now = clock.utcnow()
    logic.sweep_missed(db, now)
    visit = db.scalar(select(Visit).where(Visit.ticket_date == clock.local_date(now), Visit.ticket_no == body.ticket_no))
    if visit is None or visit.first_name.lower() != " ".join(body.first_name.split()).lower():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That ticket wasn't found. Check the number and your first name.")
    if visit.status == LEFT:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That ticket has already left the line.")
    if visit.status != WAITING:
        raise HTTPException(status.HTTP_409_CONFLICT, "You've already been called, so your visit has started.")
    visit.status, visit.finished_at = LEFT, now
    db.commit()
    background.add_task(hub.broadcast, "queue")
    return {"ticket": visit.ticket, "status": LEFT}


@router.get("/queue/summary")
def queue_summary(db: Session = Depends(get_db)):
    """Kiosk side panel: how many are waiting and the estimate for someone arriving now."""
    now = clock.utcnow()
    logic.sweep_missed(db, now)
    waiting = len(logic.waiting_line(db))
    est = _estimate_for(db, waiting, now)
    return {"waiting": waiting, "estimate_minutes": est, "message": _wait_text(est)}


@router.get("/lobby", response_model=list[LobbyCall])
def lobby(db: Session = Depends(get_db)):
    """US-05: the three most recent calls, newest first. Ticket and counter only."""
    now = clock.utcnow()
    logic.sweep_missed(db, now)
    today = clock.local_date(now)
    recent = db.scalars(select(Visit).where(Visit.ticket_date == today, Visit.called_at.is_not(None))
                        .order_by(Visit.called_at.desc(), Visit.id.desc()).limit(3)).all()
    return [LobbyCall(ticket=v.ticket, counter=v.counter, missed=v.status == GONE) for v in recent]


# ---------- Counter panel (signed-in staff): Call next, Here, Done ----------

@router.get("/queue", response_model=dict)
def queue_for_counter(db: Session = Depends(get_db), _=Depends(current_staff)):
    now = clock.utcnow()
    logic.sweep_missed(db, now)
    at_counters = db.scalars(select(Visit).where(Visit.status.in_((CALLED, SERVING))).order_by(Visit.called_at)).all()
    line = logic.waiting_line(db)
    return {"waiting": [_to_out(v).model_dump(mode="json") for v in line],
            "at_counters": [_to_out(v).model_dump(mode="json") for v in at_counters],
            "estimate_minutes": _estimate_for(db, len(line), now)}


@router.post("/queue/call-next", response_model=VisitOut)
def call_next(body: CallIn, background: BackgroundTasks, db: Session = Depends(get_db), _=Depends(current_staff)):
    now = clock.utcnow()
    logic.sweep_missed(db, now)
    visit = logic.claim_next(db, body.counter, now)
    if visit is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Nobody is waiting.")
    background.add_task(hub.broadcast, "queue")
    return _to_out(visit)


def _change(db, visit_id: int, allowed: tuple[str, ...], new_status: str, background) -> VisitOut:
    now = clock.utcnow()
    logic.sweep_missed(db, now)
    visit = db.get(Visit, visit_id)
    if visit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such ticket.")
    if visit.status not in allowed:
        raise HTTPException(status.HTTP_409_CONFLICT, f"{visit.ticket} is {visit.status}, so it can't be marked {new_status}.")
    visit.status = new_status
    if new_status == SERVING:
        visit.served_at = now
    if new_status == DONE:
        visit.served_at = visit.served_at or visit.called_at or now  # Done without Here: count from the call
        visit.finished_at = now
    db.commit()
    background.add_task(hub.broadcast, "queue")
    return _to_out(visit)


@router.post("/visits/{visit_id}/here", response_model=VisitOut)
def student_here(visit_id: int, background: BackgroundTasks, db: Session = Depends(get_db), _=Depends(current_staff)):
    """The called student reached the counter, so they won't be marked missed."""
    return _change(db, visit_id, (CALLED,), SERVING, background)


@router.post("/visits/{visit_id}/done", response_model=VisitOut)
def done(visit_id: int, background: BackgroundTasks, db: Session = Depends(get_db), _=Depends(current_staff)):
    """US-06: close the student's place; the counter can call again."""
    return _change(db, visit_id, (CALLED, SERVING), DONE, background)
