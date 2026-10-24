# Feature 4 · Weekly report & trends | Owner: Haryan Patel
# AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the owner.
"""The report reads past visits from the walk-up queue's table and never changes them.
It uses no staff data and no desk hours.

Product v1 (Deliverable 2): E7 · Weekly desk report (US-20 totals, US-21 heatmap, US-22 pick a week).
E8 (US-23 compare, US-24 problem types, US-25 CSV) comes in Product v2."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import current_staff
from app.core import clock
from app.core.database import get_db
from app.queue.models import CALLED, DONE, SERVING, WAITING, Visit

from . import calculations as calc

router = APIRouter(prefix="/api/report", tags=["Feature 4 · Weekly report & trends (Haryan)"])


def _rows(db: Session, monday: date) -> list[calc.Row]:
    start = clock.local_midnight_utc(monday)
    end = clock.local_midnight_utc(monday + timedelta(days=7))
    visits = db.scalars(select(Visit).where(Visit.arrived_at >= start, Visit.arrived_at < end,
                                            Visit.status.not_in((WAITING, CALLED, SERVING)))).all()
    return [calc.Row(arrived_at=v.arrived_at, called_at=v.called_at, served=v.status == DONE,
                     problem_type=v.problem_type) for v in visits]


def _week(week: date | None) -> date:
    """US-22: any week that has started; defaults to the current week."""
    this_monday = clock.week_start(clock.local_today())
    monday = clock.week_start(week) if week else this_monday
    if monday > this_monday:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That week hasn't started yet.")
    return monday


@router.get("/week")
def weekly_report(week: date | None = Query(None, description="Any date in the week; defaults to this week"),
                  _=Depends(current_staff), db: Session = Depends(get_db)):
    """US-20 totals and waits and US-21 heatmap for one week (US-22)."""
    monday = _week(week)
    rows = _rows(db, monday)
    return {"week_start": monday, "week_end": monday + timedelta(days=6),
            "empty": not rows, "message": "No walk-ups recorded this week" if not rows else None,
            "totals": calc.totals(rows), "heatmap": calc.heatmap(rows)}
