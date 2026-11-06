# Feature 4 · Weekly report & trends | Owner: Haryan Patel
# AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the owner.
"""The report reads past visits from the walk-up queue's table and never changes them.
It uses no staff data and no desk hours."""
import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import current_staff
from app.core import clock
from app.core.config import PROBLEM_TYPES
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
    monday = _week(week)
    rows, prev_rows = _rows(db, monday), _rows(db, monday - timedelta(days=7))
    this, prev = calc.totals(rows), calc.totals(prev_rows)
    return {"week_start": monday, "week_end": monday + timedelta(days=6),
            "empty": not rows, "message": "No walk-ups recorded this week" if not rows else None,
            "totals": this, "compare": calc.compare(this, prev, len(prev_rows)),
            "heatmap": calc.heatmap(rows), "problem_types": calc.problem_types(rows, prev_rows, PROBLEM_TYPES)}


@router.get("/week.csv")
def weekly_csv(week: date | None = Query(None), _=Depends(current_staff), db: Session = Depends(get_db)):
    """US-25: one row per visit. No first names and no ticket numbers, so no row can be traced to a student."""
    monday = _week(week)
    rows = sorted(_rows(db, monday), key=lambda r: r.arrived_at)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["date", "arrival_time", "wait_minutes", "problem_type", "served"])
    for r in rows:
        t = r.local_arrival
        w.writerow([t.date().isoformat(), t.strftime("%H:%M"),
                    "" if r.wait_min is None else round(r.wait_min, 1),
                    PROBLEM_TYPES.get(r.problem_type, r.problem_type), "yes" if r.served else "no"])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="counterpoint-week-{monday}.csv"'})
