# Feature 5 · Desk coverage | Owner: Aarya Patel
# AI disclosure: with guidance of Claude (Anthropic).
"""One test per acceptance test in US-26 to US-33. The clock is frozen on Wednesday 14 October 2026."""
import pytest

from app.auth.models import ROLE_ASSISTANT, ROLE_LEAD, ROLE_SUPERVISOR
from app.core import config
from app.coverage import notify
from app.coverage.models import ClosedDay, SupervisorNotification


@pytest.fixture
def team(make_staff, freeze):
    freeze(2026, 10, 14, 9, 0)
    return {name: make_staff(name, display_name=name.title())[1] for name in ("nate", "sam", "priya")}


def set_status(client, h, status, back_at=None, confirm=False):
    return client.patch("/api/status/me", json={"status": status, "back_at": back_at, "confirm_empty": confirm}, headers=h)


# ---- US-26 Set my status ----

def test_us26_start_of_shift(client, team, freeze):
    freeze(2026, 10, 14, 9, 30)
    r = set_status(client, team["nate"], "on_desk").json()
    assert r["label"] == "On desk" and r["since"].startswith("2026-10-14T15:30")   # 9:30 a.m. Regina = 15:30 UTC


def test_us26_going_away_with_back_at(client, team, freeze):
    set_status(client, team["sam"], "on_desk")
    set_status(client, team["nate"], "on_desk")
    freeze(2026, 10, 14, 12, 40)
    r = set_status(client, team["nate"], "at_lunch", "13:15").json()
    assert r["label"] == "At lunch" and r["since"].startswith("2026-10-14T18:40") and r["back_at"].startswith("2026-10-14T19:15")


def test_us26_no_back_at_time(client, team):
    set_status(client, team["sam"], "on_desk")
    set_status(client, team["nate"], "on_desk")
    assert set_status(client, team["nate"], "on_break").json()["back_at"] is None


def test_us26_only_real_statuses(client, team):
    set_status(client, team["nate"], "on_desk")
    r = set_status(client, team["nate"], "napping")
    assert r.status_code == 422
    assert client.get("/api/status/me", headers=team["nate"]).json()["status"] == "on_desk"


def test_us26_back_at_must_be_later(client, team, freeze):
    set_status(client, team["sam"], "on_desk")
    set_status(client, team["nate"], "on_desk")
    freeze(2026, 10, 14, 18, 38)
    r = set_status(client, team["nate"], "stepped_away", "15:30")
    assert r.status_code == 422 and "already passed" in r.text


# ---- US-27 See who's on and who's away ----

def test_us27_board(client, team, freeze, make_staff):
    freeze(2026, 10, 14, 11, 0)
    set_status(client, team["sam"], "on_desk")
    set_status(client, team["priya"], "on_desk")
    set_status(client, team["nate"], "on_desk")
    b = client.get("/api/status/board", headers=team["nate"]).json()
    assert {p["name"] for p in b["on_desk"]} == {"Sam", "Priya", "Nate"}
    freeze(2026, 10, 14, 12, 40)
    set_status(client, team["priya"], "at_lunch", "13:15")
    away = client.get("/api/status/board", headers=team["nate"]).json()["away"]
    assert away[0]["name"] == "Priya" and away[0]["label"] == "At lunch" and away[0]["overdue"] is False
    freeze(2026, 10, 14, 13, 20)
    _, h = make_staff("late", display_name="Late")
    assert client.get("/api/status/board", headers=h).json()["away"][0]["overdue"] is True
    set_status(client, team["sam"], "off_shift")
    names = [p["name"] for p in client.get("/api/status/board", headers=h).json()["on_desk"]]
    assert "Sam" not in names


# ---- US-28 Don't leave the desk empty ----

def test_us28_warning_cancel_and_confirm(client, team):
    set_status(client, team["nate"], "on_desk")
    r = set_status(client, team["nate"], "on_break")
    assert r.status_code == 409 and "only one on desk" in r.text
    assert client.get("/api/status/me", headers=team["nate"]).json()["status"] == "on_desk"   # "Stay on desk"
    assert set_status(client, team["nate"], "on_break", confirm=True).json()["status"] == "on_break"


def test_us28_no_warning_when_covered(client, team):
    set_status(client, team["sam"], "on_desk")
    set_status(client, team["nate"], "on_desk")
    assert set_status(client, team["nate"], "on_break").status_code == 200


# ---- US-29 Plan breaks ----

def test_us29_who_is_next_only_when_covered_and_resets(client, team, freeze):
    freeze(2026, 10, 14, 9, 30)
    set_status(client, team["sam"], "on_desk")
    b = client.get("/api/status/board", headers=team["nate"]).json()
    assert b["break_suggestion"] is None and b["alone"]
    freeze(2026, 10, 14, 11, 0)
    set_status(client, team["priya"], "on_desk")
    b = client.get("/api/status/board", headers=team["nate"]).json()
    assert b["break_suggestion"]["message"] == "Next break: Sam (on since 9:30 a.m.)"
    set_status(client, team["sam"], "on_break")
    freeze(2026, 10, 14, 11, 15)
    set_status(client, team["sam"], "on_desk")
    b = client.get("/api/status/board", headers=team["nate"]).json()
    assert b["break_suggestion"]["name"] == "Priya"   # Sam's time now counts from 11:15


# ---- US-30 Public coverage page ----

def test_us30_open_unattended_and_no_names(client, team, freeze):
    freeze(2026, 10, 14, 11, 0)
    set_status(client, team["sam"], "on_desk")
    set_status(client, team["priya"], "on_desk")
    r = client.get("/api/coverage")   # no sign-in
    assert r.json()["message"] == "IT desk: open, 2 assistants on."
    assert "Sam" not in r.text and "Priya" not in r.text
    set_status(client, team["sam"], "off_shift")
    freeze(2026, 10, 14, 12, 40)
    set_status(client, team["priya"], "at_lunch", confirm=True)
    assert client.get("/api/coverage").json()["message"] == "IT desk: unattended since 12:40 p.m."


# ---- US-31 When will someone be back ----

def test_us31_earliest_back_at_or_none(client, team, freeze):
    freeze(2026, 10, 14, 12, 30)
    set_status(client, team["sam"], "on_desk")
    set_status(client, team["priya"], "on_desk")
    set_status(client, team["sam"], "at_lunch")
    set_status(client, team["priya"], "on_break", confirm=True)
    assert client.get("/api/coverage").json()["back_message"] is None     # nobody gave a time
    set_status(client, team["sam"], "at_lunch", "13:30")
    set_status(client, team["priya"], "on_break", "13:15")
    assert client.get("/api/coverage").json()["back_message"] == "Someone expected back at 1:15 p.m."


# ---- US-32 Desk hours and closed days ----

def test_us32_week_closed_day_and_outside_hours(client, db, freeze):
    freeze(2026, 10, 14, 11, 0)   # Wednesday
    db.add(ClosedDay(day=__import__("datetime").date(2026, 10, 12), reason="Thanksgiving"))
    db.commit()
    week = client.get("/api/coverage").json()["week"]
    assert [d["weekday"] for d in week] == ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    assert week[2]["today"] and week[2]["opens"] == "9:30 a.m." and week[2]["closes"] == "9:00 p.m."
    assert week[5]["opens"] == "10:00 a.m." and week[5]["closes"] == "6:00 p.m."
    assert week[0]["closed"] and week[0]["reason"] == "Thanksgiving"
    freeze(2026, 10, 14, 21, 45)
    assert client.get("/api/coverage").json()["message"] == "IT desk: closed. Opens tomorrow at 9:30 a.m."


def test_us30_yesterday_doesnt_count(client, team, freeze):
    """Review fixes: a check-out forgotten yesterday doesn't keep the desk 'open', and 'since' is never yesterday's time."""
    freeze(2026, 10, 14, 18, 0)
    set_status(client, team["sam"], "on_desk")
    set_status(client, team["priya"], "on_desk")
    set_status(client, team["priya"], "off_shift")   # Sam forgets to check out
    freeze(2026, 10, 15, 9, 35)                       # Thursday, open, nobody has checked in yet
    assert client.get("/api/coverage").json()["message"] == "IT desk: unattended."


def test_us32_only_seniors_change_hours_and_bad_times_refused(client, team, make_staff):
    """Review fixes: assistants can't change the hours, and a closing time like 24:00 is refused."""
    boss = make_staff("chewy", role=ROLE_SUPERVISOR, display_name="Chewy")[1]
    hours = [{"weekday": 2, "opens": "09:30", "closes": "21:00"}]
    assert client.put("/api/desk-hours", json=hours, headers=team["sam"]).status_code == 403
    assert client.put("/api/desk-hours", json=[{"weekday": 2, "opens": "09:30", "closes": "24:00"}], headers=boss).status_code == 422
    assert client.post("/api/desk-hours/closed", json={"day": "2026-10-16", "reason": "Fall break"}, headers=boss).status_code == 201
    friday = client.get("/api/coverage").json()["week"][4]
    assert friday["closed"] and friday["reason"] == "Fall break"
    assert client.delete("/api/desk-hours/closed/2026-10-16", headers=boss).status_code == 204
    assert not client.get("/api/coverage").json()["week"][4]["closed"]


# ---- US-33 Tell the supervisor about status changes, with the time ----

def test_us33_every_change_with_its_time(client, team, freeze, make_staff):
    freeze(2026, 10, 14, 9, 31)
    set_status(client, team["sam"], "on_desk")
    set_status(client, team["nate"], "on_desk")
    freeze(2026, 10, 14, 12, 40)
    set_status(client, team["sam"], "at_lunch", "13:15")
    freeze(2026, 10, 14, 13, 12)
    set_status(client, team["sam"], "on_desk")
    freeze(2026, 10, 14, 14, 5)
    set_status(client, team["sam"], "on_break")
    freeze(2026, 10, 14, 14, 20)
    set_status(client, team["sam"], "stepped_away")
    freeze(2026, 10, 14, 17, 0)
    set_status(client, team["sam"], "off_shift")
    _, boss = make_staff("chewy", role=ROLE_SUPERVISOR, display_name="Chewy")
    feed = client.get("/api/notifications", headers=boss).json()
    sams = [i["message"] for i in reversed(feed["items"]) if i["staff_name"] == "Sam"]
    assert sams == ["Sam checked in at 9:31 a.m.",
                    "Sam went to lunch at 12:40 p.m. (back at 1:15 p.m.).",
                    "Sam came back to the desk at 1:12 p.m.",
                    "Sam went on break at 2:05 p.m.",
                    "Sam stepped away at 2:20 p.m.",
                    "Sam checked out at 5:00 p.m."]
    assert feed["unread"] == 7 and all(i["at"] for i in feed["items"])


def test_us33_no_change_no_notification(client, team, db):
    set_status(client, team["nate"], "on_desk")
    set_status(client, team["nate"], "on_desk")
    assert db.query(SupervisorNotification).count() == 1


def test_us33_whole_team_sees_feed_only_seniors_mark_read(client, team, make_staff):
    set_status(client, team["nate"], "on_desk")
    feed = client.get("/api/notifications", headers=team["sam"]).json()          # an assistant
    assert [i["message"] for i in feed["items"]] == ["Nate checked in at 9:00 a.m."]
    assert feed["can_mark_read"] is False and feed["unread"] == 0
    assert client.post("/api/notifications/read", headers=team["sam"]).status_code == 403
    _, lead = make_staff("lead", role=ROLE_LEAD)
    lead_feed = client.get("/api/notifications", headers=lead).json()
    assert lead_feed["can_mark_read"] is True and lead_feed["unread"] == 1
    assert client.get("/api/notifications").status_code == 401                    # not signed in


def test_us33_mark_read(client, team, make_staff):
    set_status(client, team["nate"], "on_desk")
    _, boss = make_staff("chewy", role=ROLE_SUPERVISOR)
    client.post("/api/notifications/read", headers=boss)
    assert client.get("/api/notifications", headers=boss).json()["unread"] == 0


def test_us33_email_when_configured(client, team, make_staff, monkeypatch):
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout): sent.append({"host": host})
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, u, p): pass
        def send_message(self, msg): sent[-1].update(to=msg["To"], subject=msg["Subject"], body=msg.get_content())

    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.ca")
    monkeypatch.setattr(notify.smtplib, "SMTP", FakeSMTP)
    make_staff("chewy", role=ROLE_SUPERVISOR, email="chewy@usask.ca")
    set_status(client, team["nate"], "on_desk")
    assert sent[0]["to"] == "chewy@usask.ca"
    assert sent[0]["subject"] == "Counterpoint: Nate checked in at 9:00 a.m."
    assert "Time: Wednesday 14 October 2026, 09:00" in sent[0]["body"]


def test_us33_email_failure_never_blocks_status(client, team, make_staff, monkeypatch):
    def boom(*a, **k):
        raise OSError("mail server down")
    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.ca")
    monkeypatch.setattr(notify.smtplib, "SMTP", boom)
    make_staff("chewy", role=ROLE_SUPERVISOR, email="chewy@usask.ca")
    assert set_status(client, team["nate"], "on_desk").status_code == 200


def test_status_needs_sign_in(client):
    assert client.patch("/api/status/me", json={"status": "on_desk"}).status_code == 401
    assert client.get("/api/coverage").status_code == 200
