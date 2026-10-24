# Feature 1 (E1): kiosk routes, no sign-in needed | Owner: Mohit Sawant
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import clock
from app.core.database import get_db
from app.core.realtime import hub

from . import logic
from .models import LEFT, WAITING, Visit
from .schemas import CheckIn, CheckInOut, LeaveIn

router = APIRouter(prefix="/api", tags=["Feature 1 · Walk-up queue (Mohit)"])


def _find_today(db: Session, ticket_no: int, now) -> Visit | None:
    return db.scalar(select(Visit).where(Visit.ticket_date == clock.local_date(now), Visit.ticket_no == ticket_no))


@router.post("/visits", response_model=CheckInOut, status_code=status.HTTP_201_CREATED)
def check_in(body: CheckIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    """US-01 and US-02: get a ticket number, a place in line and an estimated wait."""
    now = clock.utcnow()
    for _ in range(3):   # two kiosks at the same moment could pick the same number, so try again
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
    minutes = logic.estimate(db, ahead, now)
    background.add_task(hub.broadcast, "queue")
    return CheckInOut(ticket=visit.ticket, place=ahead + 1, estimate_minutes=minutes, message=logic.wait_text(minutes))


@router.get("/visits/place")
def check_my_place(ticket_no: int = Query(ge=1), db: Session = Depends(get_db)):
    """US-02: where am I now? Returns a place and an estimate, nothing personal."""
    now = clock.utcnow()
    visit = _find_today(db, ticket_no, now)
    if visit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That ticket wasn't found today.")
    if visit.status != WAITING:
        return {"ticket": visit.ticket, "status": visit.status, "place": None, "counter": visit.counter}
    ahead = [v.id for v in logic.waiting_line(db)].index(visit.id)
    minutes = logic.estimate(db, ahead, now)
    return {"ticket": visit.ticket, "status": WAITING, "place": ahead + 1,
            "estimate_minutes": minutes, "message": logic.wait_text(minutes)}


@router.post("/visits/leave")
def leave_line(body: LeaveIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    """US-03: take myself out of the line with my ticket number and first name."""
    now = clock.utcnow()
    visit = _find_today(db, body.ticket_no, now)
    typed = " ".join(body.first_name.split()).lower()
    if visit is None or visit.first_name.lower() != typed or visit.status == LEFT:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "That ticket wasn't found. Check the number and your first name.")
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
    waiting = len(logic.waiting_line(db))
    minutes = logic.estimate(db, waiting, now)
    return {"waiting": waiting, "estimate_minutes": minutes, "message": logic.wait_text(minutes)}
