# Feature 4 · Weekly report & trends | Owner: Haryan Patel
# AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the owner.
"""One test per acceptance test in US-20 to US-25. Today is frozen at Tuesday 6 October 2026,
so the week of 28 September is the last complete week."""
import csv
import io
from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.config import LOCAL_TZ
from app.queue.models import DONE, GONE, LEFT, Visit
from app.report import calculations as calc


@pytest.fixture
def chewy(make_staff, freeze):
    freeze(2026, 10, 6, 9, 0)
    return make_staff("chewy", role="supervisor")[1]


def visit(db, day, hour, minute=0, wait=5, status=DONE, ptype="wifi", n=[0]):
    """day is (month, day) or a date."""
    n[0] += 1
    d = day if isinstance(day, date) else date(2026, *day)
    arrived = datetime(d.year, d.month, d.day, hour, minute, tzinfo=LOCAL_TZ).astimezone(timezone.utc)
    called = arrived + timedelta(minutes=wait) if status in (DONE, GONE) else None
    db.add(Visit(ticket_date=arrived.date(), ticket_no=n[0], first_name="Student", problem_type=ptype,
                 status=status, arrived_at=arrived, called_at=called, counter="Counter 1" if called else None,
                 finished_at=arrived + timedelta(minutes=wait + 10)))


def week_of(db, start=(9, 28), served=111, never_served=9, ptype="wifi"):
    """Spread visits over Monday-Friday of the week starting `start`."""
    monday = date(2026, *start)
    for i in range(served):
        visit(db, monday + timedelta(days=i % 5), 10 + i % 8, ptype=ptype)
    for i in range(never_served):
        visit(db, monday + timedelta(days=i % 5), 12, status=LEFT if i % 2 else GONE)
    db.commit()


# ---- US-20 Weekly totals and waits ----

def test_us20_totals(client, db, chewy):
    week_of(db)
    t = client.get("/api/report/week", params={"week": "2026-09-28"}, headers=chewy).json()["totals"]
    assert (t["walk_ups"], t["served"], t["walk_aways"], t["walk_away_pct"]) == (120, 111, 9, 7.5)


def test_us20_wait_times_nearest_rank():
    rows = [calc.Row(arrived_at=datetime(2026, 9, 29, 16, tzinfo=timezone.utc),
                     called_at=datetime(2026, 9, 29, 16, tzinfo=timezone.utc) + timedelta(minutes=w),
                     served=True, problem_type="wifi") for w in (5, 8, 10, 12, 30)]
    t = calc.totals(rows)
    assert t["median_wait"] == 10 and t["p90_wait"] == 30


def test_us20_walk_aways_dont_count_as_waits(client, db, chewy):
    visit(db, (9, 29), 10, wait=10)
    visit(db, (9, 29), 11, wait=25, status=LEFT)
    db.commit()
    t = client.get("/api/report/week", params={"week": "2026-09-28"}, headers=chewy).json()["totals"]
    assert t["walk_aways"] == 1 and t["median_wait"] == 10 and t["p90_wait"] == 10


# ---- US-21 Busiest-hours heatmap ----

def test_us21_grid_shading_and_quiet_hours(client, db, chewy):
    for _ in range(6):
        visit(db, (9, 29), 13, 20)    # Tuesday 1-2 p.m.
    visit(db, (9, 30), 10)
    db.commit()
    h = client.get("/api/report/week", params={"week": "2026-09-28"}, headers=chewy).json()["heatmap"]
    assert [r["day"] for r in h["rows"]] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    assert h["hours"] == list(range(9, 21))
    assert h["peak"] == {"day": "Tue", "hour": 13, "count": 6} and h["max"] == 6
    assert h["rows"][0]["counts"] == [0] * 12


# ---- US-22 Pick any past week ----

def test_us22_choose_week(client, db, chewy):
    week_of(db, start=(9, 21), served=10, never_served=0)
    r = client.get("/api/report/week", params={"week": "2026-09-23"}, headers=chewy).json()
    assert r["week_start"] == "2026-09-21" and r["totals"]["walk_ups"] == 10


def test_us22_no_future_weeks(client, chewy):
    r = client.get("/api/report/week", params={"week": "2026-10-12"}, headers=chewy)
    assert r.status_code == 400 and "hasn't started" in r.text


def test_us22_empty_week(client, chewy):
    r = client.get("/api/report/week", params={"week": "2026-08-03"}, headers=chewy).json()
    assert r["empty"] and r["message"] == "No walk-ups recorded this week"


# ---- US-23 Compare with the previous week ----

def test_us23_change_and_direction(client, db, chewy):
    week_of(db, start=(9, 21), served=95, never_served=5)    # 100 walk-ups
    week_of(db, start=(9, 28), served=111, never_served=9)   # 120 walk-ups
    c = client.get("/api/report/week", params={"week": "2026-09-28"}, headers=chewy).json()["compare"]
    assert c["changes"]["walk_ups"] == {"diff": 20, "pct": 20, "verdict": None}
    assert c["changes"]["walk_aways"]["verdict"] == "worse"


def test_us23_lower_wait_is_better():
    this, prev = {"median_wait": 8}, {"median_wait": 12}
    assert calc.compare(this, prev, prev_walkups=50)["changes"]["median_wait"]["verdict"] == "better"


def test_us23_no_previous_week(client, db, chewy):
    week_of(db)
    c = client.get("/api/report/week", params={"week": "2026-09-28"}, headers=chewy).json()["compare"]
    assert c == {"available": False, "message": "No previous week to compare"}


# ---- US-24 What people come in for ----

def test_us24_breakdown_biggest_change_and_adds_up(client, db, chewy):
    week_of(db, start=(9, 21), served=10, never_served=0, ptype="wifi")
    week_of(db, start=(9, 21), served=20, never_served=0, ptype="mfa")
    week_of(db, start=(9, 28), served=25, never_served=0, ptype="wifi")
    week_of(db, start=(9, 28), served=30, never_served=0, ptype="mfa")
    r = client.get("/api/report/week", params={"week": "2026-09-28"}, headers=chewy).json()
    p = r["problem_types"]
    assert [i["label"] for i in p["items"]] == ["MFA & sign-in", "Wi-Fi (eduroam)"]
    assert p["biggest_increase"] == "wifi"
    assert sum(i["count"] for i in p["items"]) == r["totals"]["walk_ups"]


# ---- US-25 Download the week as CSV ----

def test_us25_download_no_names_matches_report(client, db, chewy):
    week_of(db)
    r = client.get("/api/report/week.csv", params={"week": "2026-09-28"}, headers=chewy)
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows[0] == ["date", "arrival_time", "wait_minutes", "problem_type", "served"]
    assert len(rows) - 1 == 120
    assert "Student" not in r.text and "#" not in r.text
    assert "attachment" in r.headers["content-disposition"]


def test_report_needs_sign_in(client):
    assert client.get("/api/report/week").status_code == 401


# ---- Defects found while testing Product v2 (regression tests) ----

def test_us21_early_and_late_visits_stay_on_the_grid(client, db, chewy):
    """D-R1: US-32 lets seniors change desk hours, but the heatmap only had 9 a.m.-9 p.m. columns,
    so visits before 9 or after 9 p.m. vanished and the grid no longer added up to the walk-ups."""
    visit(db, (9, 29), 8, 30)
    visit(db, (9, 29), 21, 15)
    visit(db, (9, 30), 13)
    db.commit()
    rep = client.get("/api/report/week", params={"week": "2026-09-28"}, headers=chewy).json()
    h = rep["heatmap"]
    assert sum(sum(r["counts"]) for r in h["rows"]) == rep["totals"]["walk_ups"] == 3
    assert h["hours"][0] == 8 and h["hours"][-1] == 21
