# Feature 5 · Desk coverage · E11 Time away from the desk | Owner: Aarya Patel
# AI disclosure: with guidance of Claude (Anthropic).
"""One test per acceptance test in US-34 to US-37. The clock is frozen; Regina is UTC-6 all year."""
import pytest

from app.auth.models import ROLE_LEAD, ROLE_SUPERVISOR
from app.core import config
from app.coverage import notify
from app.coverage.models import AbsenceReport, TimeOffRequest
from tests.conftest import PASSWORD


@pytest.fixture
def mail(monkeypatch):
    """A fake mail server that records what would have been sent."""
    sent = []

    class FakeSMTP:
        def __init__(self, host, port, timeout): sent.append({})
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def starttls(self): pass
        def login(self, u, p): pass
        def send_message(self, msg): sent[-1].update(to=msg["To"], subject=msg["Subject"], body=msg.get_content())

    monkeypatch.setattr(config, "SMTP_HOST", "smtp.example.ca")
    monkeypatch.setattr(notify.smtplib, "SMTP", FakeSMTP)
    return sent


@pytest.fixture
def people(make_staff, freeze):
    freeze(2026, 10, 14, 9, 0)
    _, nate = make_staff("nate", role=ROLE_LEAD, display_name="Nate", email="nate@usask.ca")
    _, sam = make_staff("sam", display_name="Sam", email="sam@usask.ca")
    _, boss = make_staff("chewy", role=ROLE_SUPERVISOR, display_name="Chewy", email="chewy@usask.ca")
    _, palak = make_staff("palak", display_name="Palak")      # another assistant: what the rest of the team sees
    return {"nate": nate, "sam": sam, "chewy": boss, "palak": palak}


def sign_in(client, username):
    token = client.post("/api/auth/login", json={"username": username, "password": PASSWORD}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def report(client, h, kind="sick", day="2026-10-14", starts="13:00", ends="17:00", note=""):
    return client.post("/api/absences", json={"kind": kind, "day": day, "starts": starts, "ends": ends, "note": note}, headers=h)


def request(client, h, start="2026-11-02", end="2026-11-04", reason="Midterm week"):
    return client.post("/api/time-off", json={"start": start, "end": end, "reason": reason}, headers=h)


def decide(client, h, rid, approve=True, reason=""):
    return client.post(f"/api/time-off/{rid}/decision", json={"approve": approve, "reason": reason}, headers=h)


# ---- US-34 Report sick or an emergency ----

def test_us34_saved_with_its_time(client, people, freeze, db):
    freeze(2026, 10, 14, 9, 12)
    r = report(client, people["nate"])
    assert r.status_code == 201 and r.json()["reported_time"] == "9:12 a.m." and r.json()["late"] is False
    saved = db.query(AbsenceReport).one()
    assert saved.reported_at.isoformat().startswith("2026-10-14T15:12")       # 9:12 a.m. Regina
    assert saved.shift_start.isoformat().startswith("2026-10-14T19:00")       # 1:00 p.m. Regina


def test_us34_supervisor_emailed_and_email_failure_never_blocks(client, people, freeze, mail, monkeypatch):
    freeze(2026, 10, 14, 9, 12)
    report(client, people["nate"])
    assert mail[0]["to"] == "chewy@usask.ca"
    assert mail[0]["subject"] == "Counterpoint: Nate reported sick at 9:12 a.m. (shift today 1:00–5:00 p.m.)"
    assert "Time: Wednesday 14 October 2026, 09:12" in mail[0]["body"]

    def boom(*a, **k):
        raise OSError("mail server down")
    monkeypatch.setattr(notify.smtplib, "SMTP", boom)
    assert report(client, people["sam"], kind="emergency").status_code == 201


def test_us34_no_medical_details(client, people):
    assert report(client, people["sam"], note="x" * 201).status_code == 422
    report(client, people["sam"], kind="emergency", note="Family emergency, back tomorrow")
    seen_by_lead = client.get("/api/time-away", headers=people["nate"]).json()
    assert seen_by_lead["reports"][0]["kind_label"] == "Emergency" and "Family" in seen_by_lead["reports"][0]["note"]
    assert "reports" not in client.get("/api/time-away", headers=people["palak"]).json()


def test_us34_late_notice(client, people, freeze):
    freeze(2026, 10, 14, 13, 20)
    r = report(client, people["nate"]).json()
    assert r["late"] is True and r["message"].endswith("after the shift started")


def test_us34_only_real_kinds_and_times(client, people):
    assert report(client, people["sam"], kind="vacation").status_code == 422
    assert report(client, people["sam"], starts="17:00", ends="13:00").status_code == 422
    assert report(client, people["sam"], day="2026-10-13").status_code == 422


# ---- US-35 Request time off ----

def test_us35_request_sent(client, people, freeze, mail):
    freeze(2026, 10, 14, 10, 5)
    r = request(client, people["nate"])
    assert r.status_code == 201 and r.json()["status"] == "pending"
    assert mail[0]["to"] == "chewy@usask.ca"
    assert mail[0]["subject"] == "Counterpoint: Nate requested time off for 2–4 November (sent 10:05 a.m.)"
    mine = client.get("/api/time-away", headers=people["nate"]).json()["my_requests"][0]
    assert mine["status"] == "pending" and mine["requested_time"] == "10:05 a.m."


def test_us35_sensible_dates_only(client, people):
    assert request(client, people["sam"], start="2026-10-13", end="2026-10-15").status_code == 422
    assert "past" in request(client, people["sam"], start="2026-10-13", end="2026-10-15").text
    assert request(client, people["sam"], start="2026-11-04", end="2026-11-02").status_code == 422
    assert request(client, people["sam"], reason="  ").status_code == 422


def test_us35_cancel_while_pending(client, people, mail, db):
    rid = request(client, people["sam"]).json()["id"]
    assert client.post(f"/api/time-off/{rid}/cancel", headers=people["sam"]).json()["status"] == "cancelled"
    assert mail[-1]["subject"].startswith("Counterpoint: Sam cancelled the time-off request for 2–4 November")
    rid2 = request(client, people["sam"]).json()["id"]
    decide(client, people["chewy"], rid2)
    assert client.post(f"/api/time-off/{rid2}/cancel", headers=people["sam"]).status_code == 409
    assert client.post(f"/api/time-off/{rid2}/cancel", headers=people["nate"]).status_code == 403   # not his


# ---- US-36 Get a decision on my time off ----

def test_us36_approved(client, people, freeze, mail):
    rid = request(client, people["nate"]).json()["id"]
    freeze(2026, 10, 14, 15, 40)
    r = decide(client, people["chewy"], rid).json()
    assert r["status"] == "approved" and r["decided_by"] == "Chewy" and r["decided_time"] == "3:40 p.m."
    assert mail[-1]["to"] == "nate@usask.ca"
    assert mail[-1]["subject"] == "Counterpoint: Your time off for 2–4 November was approved at 3:40 p.m."


def test_us36_declined_needs_a_reason(client, people, mail):
    rid = request(client, people["sam"]).json()["id"]
    assert decide(client, people["chewy"], rid, approve=False).status_code == 422
    decide(client, people["chewy"], rid, approve=False, reason="Two others are already off that week")
    mine = client.get("/api/time-away", headers=people["sam"]).json()["my_requests"][0]
    assert mine["status"] == "declined" and mine["decision_reason"] == "Two others are already off that week"
    assert "Reason: Two others are already off that week" in mail[-1]["subject"]


def test_us36_not_your_own_and_only_seniors(client, people):
    own = request(client, people["nate"]).json()["id"]
    assert decide(client, people["nate"], own).status_code == 403        # a shift lead, but it's his own
    sams = request(client, people["sam"]).json()["id"]
    assert decide(client, people["sam"], sams).status_code == 403        # assistants never decide
    assert decide(client, people["nate"], sams).status_code == 200       # another person's: allowed


def test_us36_decided_once(client, people, db):
    rid = request(client, people["sam"]).json()["id"]
    decide(client, people["chewy"], rid)
    assert decide(client, people["nate"], rid, approve=False, reason="No").status_code == 409
    assert db.get(TimeOffRequest, rid).status == "approved"


# ---- US-37 See who's away in the next two weeks ----

def test_us37_next_14_days(client, people, freeze, make_staff):
    _, priya = make_staff("priya", display_name="Priya")
    rid = request(client, priya).json()["id"]
    decide(client, people["chewy"], rid)
    freeze(2026, 11, 1, 9, 0)                       # 1 November: sign in again (sign-ins last 12 hours)
    sam, nate = sign_in(client, "sam"), sign_in(client, "nate")
    report(client, sam, day="2026-11-01")
    days = client.get("/api/time-away", headers=nate).json()["upcoming"]
    assert len(days) == 14 and days[0]["date"] == "2026-11-01"
    away = {d["date"]: [p["name"] for p in d["away"]] for d in days if d["away"]}
    assert away == {"2026-11-01": ["Sam"], "2026-11-02": ["Priya"], "2026-11-03": ["Priya"], "2026-11-04": ["Priya"]}


def test_us37_names_and_dates_only(client, people):
    report(client, people["sam"], note="Migraine")
    body = client.get("/api/time-away", headers=people["palak"]).text
    assert "Sam" in body and "Migraine" not in body and "sick" not in body.lower()


def test_us37_pending_isnt_away(client, people, make_staff):
    _, oliver = make_staff("oliver", display_name="Oliver")
    request(client, oliver, start="2026-10-15", end="2026-10-15")
    days = client.get("/api/time-away", headers=people["nate"]).json()["upcoming"]
    assert not any(p["name"] == "Oliver" for d in days for p in d["away"])


def test_time_away_needs_sign_in(client):
    assert client.get("/api/time-away").status_code == 401
    assert client.post("/api/time-off", json={"start": "2026-11-02", "end": "2026-11-02", "reason": "x"}).status_code == 401



# ---- Defects found while testing Product v2 (regression tests) ----

def test_us34_same_shift_reported_once(client, people, mail):
    """D-A1: reporting the same shift twice saved two reports and emailed the supervisor twice."""
    assert report(client, people["sam"]).status_code == 201
    r = report(client, people["sam"], kind="emergency", starts="14:00", ends="16:00")
    assert r.status_code == 409 and "already reported" in r.text
    assert len(mail) == 1


def test_us35_overlapping_request_refused(client, people, mail):
    """D-A2: a second request overlapping a Pending or Approved one was accepted, so the same days
    showed up twice for the supervisor. A cancelled request no longer blocks the days."""
    rid = request(client, people["sam"]).json()["id"]
    r = request(client, people["sam"], start="2026-11-04", end="2026-11-06")
    assert r.status_code == 409 and "already" in r.text
    client.post(f"/api/time-off/{rid}/cancel", headers=people["sam"])
    assert request(client, people["sam"], start="2026-11-04", end="2026-11-06").status_code == 201
