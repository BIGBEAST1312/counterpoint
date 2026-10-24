# Feature 5 · Desk coverage | Owner: Aarya Patel
# AI disclosure: with guidance of Claude (Anthropic).
"""One test per acceptance test in US-26 to US-29 and US-33 (Product v1). US-30 to US-32 come in Product v2.
The clock is frozen on Wednesday 14 October 2026."""
import pytest

from app.auth.models import ROLE_LEAD, ROLE_SUPERVISOR
from app.core import config
from app.coverage import notify
from app.coverage.models import SupervisorNotification


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
    assert client.get("/api/status/board").status_code == 401
