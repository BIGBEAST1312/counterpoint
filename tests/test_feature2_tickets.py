# Feature 2 · Ticket drafts & shift handover | Owner: Hetank Patel
# AI use: Used AI for concept explanations, understanding syntax, and general debugging guidance.
"""One test per acceptance test in US-07 to US-13."""
from app.tickets.models import HandoverNote, TicketDraft

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
    draft(client, h)
    draft(client, h)
    assert client.get("/api/handover", headers=h).json()["my_unraised_drafts"] == 2


# ---- US-10 Write a handover note ----

def test_us10_save_a_note(client, make_staff):
    _, h = make_staff("rurik", display_name="Rurik")
    r = client.post("/api/handover", json={"text": "Printer 2 jammed; Facilities called, no fix yet",
                                           "category": "Equipment", "urgent": True}, headers=h)
    assert r.status_code == 201
    assert r.json()["author"] == "Rurik" and r.json()["created_at"] and r.json()["urgent"]


def test_us10_categories(client, make_staff):
    _, h = make_staff("rurik")
    for c in ("Follow-up", "Equipment", "FYI"):
        assert client.post("/api/handover", json={"text": "x", "category": c}, headers=h).status_code == 201
    assert client.post("/api/handover", json={"text": "x", "category": "Gossip"}, headers=h).status_code == 422


def test_us10_length(client, make_staff, db):
    _, h = make_staff("rurik")
    assert "Write something" in client.post("/api/handover", json={"text": "  "}, headers=h).text
    assert "500 characters" in client.post("/api/handover", json={"text": "x" * 501}, headers=h).text
    assert db.query(HandoverNote).count() == 0


# ---- US-11 Read what the last shift left ----

def test_us11_urgent_first_then_newest(client, make_staff, freeze):
    freeze(2026, 10, 14, 9, 0)
    _, h = make_staff("day", display_name="Dana")
    client.post("/api/handover", json={"text": "old FYI"}, headers=h)
    freeze(2026, 10, 14, 10, 0)
    client.post("/api/handover", json={"text": "urgent printer", "urgent": True, "category": "Equipment"}, headers=h)
    freeze(2026, 10, 14, 11, 0)
    client.post("/api/handover", json={"text": "new FYI"}, headers=h)
    notes = client.get("/api/handover", headers=h).json()["notes"]
    assert [n["text"] for n in notes] == ["urgent printer", "new FYI", "old FYI"]
    assert notes[0]["author"] == "Dana" and notes[0]["created_at"]


def test_us11_nothing_open(client, make_staff):
    _, h = make_staff("rurik")
    assert client.get("/api/handover", headers=h).json()["message"] == "Nothing handed over."


# ---- US-12 Resolve a note ----

def test_us12_resolve_and_history(client, make_staff):
    _, h = make_staff("rurik", display_name="Rurik")
    n = client.post("/api/handover", json={"text": "Printer 2", "category": "Equipment"}, headers=h).json()
    r = client.patch(f"/api/handover/{n['id']}/resolve", headers=h).json()
    assert r["resolved_by"] == "Rurik" and r["resolved_at"]
    assert client.get("/api/handover", headers=h).json()["notes"] == []
    assert [x["text"] for x in client.get("/api/handover/resolved", headers=h).json()] == ["Printer 2"]


# ---- US-13 Follow up escalations ----

def test_us13_appears_ticks_off_and_solved_stays_off(client, make_staff):
    _, h = make_staff("rurik", display_name="Rurik")
    esc = draft(client, h, outcome="Escalated").json()
    ret = draft(client, h, outcome="Student returning").json()
    draft(client, h, outcome="Solved")
    assert {d["id"] for d in client.get("/api/followups", headers=h).json()} == {esc["id"], ret["id"]}
    r = client.post(f"/api/drafts/{esc['id']}/followed-up", json={"note": "Called student, fixed"}, headers=h).json()
    assert r["follow_up_note"] == "Called student, fixed" and r["followed_up_by"] == "Rurik"
    assert [d["id"] for d in client.get("/api/followups", headers=h).json()] == [ret["id"]]


def test_tickets_need_sign_in(client):
    assert client.post("/api/drafts", json=DRAFT).status_code == 401
    assert client.get("/api/handover").status_code == 401


# ---- Defects found while testing Product v2 (regression tests) ----

def test_us08_raised_draft_keeps_its_number(client, make_staff):
    """D-H1: a raised draft is locked (US-07 test 4), but its TeamDynamix number could be overwritten."""
    _, h = make_staff("rurik")
    d = draft(client, h).json()
    assert client.patch(f"/api/drafts/{d['id']}/tdx", json={"tdx_number": "10482771"}, headers=h).status_code == 200
    r = client.patch(f"/api/drafts/{d['id']}/tdx", json={"tdx_number": "10482772"}, headers=h)
    assert r.status_code == 409
    assert client.get("/api/drafts", headers=h).json()[0]["tdx_number"] == "10482771"


def test_us13_follow_up_needs_a_real_note_and_happens_once(client, make_staff):
    """D-H2: a note of only spaces was accepted (and saved empty), and a second follow-up
    overwrote who followed up and when."""
    _, h = make_staff("rurik")
    d = draft(client, h, outcome="Escalated").json()
    url = f"/api/drafts/{d['id']}/followed-up"
    assert client.post(url, json={"note": "   "}, headers=h).status_code == 422
    assert client.post(url, json={"note": "Called the student back"}, headers=h).status_code == 200
    r = client.post(url, json={"note": "Again"}, headers=h)
    assert r.status_code == 409
    assert client.get("/api/drafts", headers=h).json()[0]["follow_up_note"] == "Called the student back"
