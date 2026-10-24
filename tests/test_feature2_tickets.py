# Feature 2 · Ticket drafts & shift handover | Owner: Hetank Patel
# AI use: Used AI for concept explanations, understanding syntax, and general debugging guidance.
"""One test per acceptance test in US-07 to US-09 (Product v1). US-10 to US-13 come in Product v2."""
from app.tickets.models import TicketDraft

DRAFT = {"problem_type": "wifi", "reported": "Can't connect to eduroam on Android 14",
         "what_i_did": "Removed the network, re-added it with the USask certificate settings", "outcome": "Solved"}


def draft(client, h, **changes):
    return client.post("/api/drafts", json={**DRAFT, **changes}, headers=h)


# ---- US-07 Draft a ticket ----

def test_us07_ready_to_paste(client, make_staff):
    _, h = make_staff("rurik")
    r = draft(client, h)
    assert r.status_code == 201
    text = r.json()["text"]
    assert text.startswith("Summary: Wi-Fi (eduroam): Can't connect to eduroam on Android 14")
    assert "Student reported:" in text and "What I did:" in text and "Outcome: Solved" in text


def test_us07_required_fields(client, make_staff, db):
    _, h = make_staff("rurik")
    r = draft(client, h, what_i_did=" ")
    assert r.status_code == 422 and "What I did" in r.text
    assert draft(client, h, outcome="").status_code == 422
    assert db.query(TicketDraft).count() == 0


def test_us07_only_three_outcomes(client, make_staff):
    _, h = make_staff("rurik")
    for ok in ("Solved", "Escalated", "Student returning"):
        assert draft(client, h, outcome=ok).status_code == 201
    r = draft(client, h, outcome="Referred")
    assert r.status_code == 422 and "Solved, Escalated or Student returning" in r.text


def test_us07_fix_before_raising_then_locked(client, make_staff):
    _, h = make_staff("rurik")
    d = draft(client, h).json()
    r = client.put(f"/api/drafts/{d['id']}", json={**DRAFT, "what_i_did": "Re-added eduroam, then rebooted"}, headers=h)
    assert r.status_code == 200 and "rebooted" in r.json()["text"]
    client.patch(f"/api/drafts/{d['id']}/tdx", json={"tdx_number": "10482771"}, headers=h)
    r = client.put(f"/api/drafts/{d['id']}", json=DRAFT, headers=h)
    assert r.status_code == 409 and "locked" in r.text


# ---- US-08 Record the TeamDynamix number ----

def test_us08_mark_as_raised(client, make_staff):
    _, h = make_staff("rurik")
    d = draft(client, h).json()
    r = client.patch(f"/api/drafts/{d['id']}/tdx", json={"tdx_number": "10482771"}, headers=h).json()
    assert r["tdx_number"] == "10482771" and r["raised_at"] is not None and r["locked"]


def test_us08_digits_only(client, make_staff):
    _, h = make_staff("rurik")
    d = draft(client, h).json()
    r = client.patch(f"/api/drafts/{d['id']}/tdx", json={"tdx_number": "abc"}, headers=h)
    assert r.status_code == 422 and "digits only" in r.text


def test_us08_no_duplicates(client, make_staff):
    _, h = make_staff("rurik")
    a, b = draft(client, h).json(), draft(client, h).json()
    client.patch(f"/api/drafts/{a['id']}/tdx", json={"tdx_number": "10482771"}, headers=h)
    r = client.patch(f"/api/drafts/{b['id']}/tdx", json={"tdx_number": "10482771"}, headers=h)
    assert r.status_code == 409 and "already used" in r.text


# ---- US-09 See my unraised drafts ----

def test_us09_list_oldest_first_and_clears(client, make_staff, freeze):
    freeze(2026, 10, 14, 17, 0)
    _, h = make_staff("rurik")
    first = draft(client, h, reported="First").json()
    freeze(2026, 10, 14, 17, 30)
    second = draft(client, h, reported="Second").json()
    third = draft(client, h, reported="Third").json()
    client.patch(f"/api/drafts/{second['id']}/tdx", json={"tdx_number": "555"}, headers=h)
    ids = [d["id"] for d in client.get("/api/drafts", params={"raised": False}, headers=h).json()]
    assert ids == [first["id"], third["id"]]
    client.patch(f"/api/drafts/{first['id']}/tdx", json={"tdx_number": "556"}, headers=h)
    assert [d["id"] for d in client.get("/api/drafts", params={"raised": False}, headers=h).json()] == [third["id"]]


def test_us09_end_of_shift_reminder(client, make_staff):
    _, h = make_staff("rurik")
    raised = draft(client, h).json()
    draft(client, h)
    draft(client, h)
    client.patch(f"/api/drafts/{raised['id']}/tdx", json={"tdx_number": "10482771"}, headers=h)
    r = client.get("/api/drafts/reminder", headers=h).json()
    assert r["my_unraised_drafts"] == 2 and r["message"] == "You still have 2 drafts to raise in TeamDynamix."


def test_tickets_need_sign_in(client):
    assert client.post("/api/drafts", json=DRAFT).status_code == 401
    assert client.get("/api/drafts/reminder").status_code == 401
