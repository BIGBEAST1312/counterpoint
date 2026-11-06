# Feature 3 · Fix guides | Owner: Priyesh Patel
# AI disclosure: Used AI for concept explanations, understanding syntax and debugging guidance.
"""One test per acceptance test in US-14 to US-19. (US-16's tick boxes live in the browser;
the API test checks the numbered steps and 'before you start' they are built from.)"""
from app.auth.models import ROLE_LEAD
from app.guides.models import Guide

MFA = {"title": "MFA: re-register a new phone", "problem_type": "mfa",
       "before_you_start": "Does the student have their new phone with them?",
       "steps": [f"Step {i}" for i in range(1, 8)]}


def make(client, h, **kw):
    return client.post("/api/guides", json={**MFA, **kw}, headers=h)


# ---- US-14 Browse guides by problem type ----

def test_us14_by_type_alphabetical(client, make_staff):
    _, h = make_staff("noah")
    make(client, h, title="eduroam on Android 14", problem_type="wifi")
    make(client, h, title="Connect a Mac to eduroam", problem_type="wifi")
    make(client, h)  # an MFA guide, not shown
    r = client.get("/api/guides", params={"problem_type": "wifi"}, headers=h).json()
    assert [g["title"] for g in r["guides"]] == ["Connect a Mac to eduroam", "eduroam on Android 14"]
    assert all(g["reviewed_at"] for g in r["guides"])


def test_us14_empty_type(client, make_staff):
    _, h = make_staff("noah")
    assert client.get("/api/guides", params={"problem_type": "printing"}, headers=h).json()["message"] == "No guides for this yet."


def test_us14_flagged_guides_stand_out(client, make_staff):
    _, h = make_staff("noah")
    g = make(client, h, title="eduroam on Android 14", problem_type="wifi").json()
    client.post(f"/api/guides/{g['id']}/flag", json={"reason": "Android 15 menu changed"}, headers=h)
    assert client.get("/api/guides", params={"problem_type": "wifi"}, headers=h).json()["guides"][0]["flagged"]


# ---- US-15 Search guides ----

def test_us15_keyword(client, make_staff):
    _, h = make_staff("noah")
    make(client, h, title="eduroam on Android 14", problem_type="wifi")
    titles = [g["title"] for g in client.get("/api/guides/search", params={"q": "android wifi"}, headers=h).json()["guides"]]
    assert titles == ["eduroam on Android 14"]


def test_us15_title_matches_first(client, make_staff):
    _, h = make_staff("noah")
    make(client, h, title="Outlook keeps asking for a password", problem_type="email", steps=["Clear cached credentials"])
    make(client, h, title="Reset a password", problem_type="password", steps=["Use the reset page"])
    make(client, h, title="Set up Outlook on a Mac", problem_type="email", steps=["Sign in with your password"])
    titles = [g["title"] for g in client.get("/api/guides/search", params={"q": "password"}, headers=h).json()["guides"]]
    assert titles[-1] == "Set up Outlook on a Mac"   # only matched in its steps


def test_us15_no_results(client, make_staff):
    _, h = make_staff("noah")
    r = client.get("/api/guides/search", params={"q": "fax machine"}, headers=h).json()
    assert r["guides"] == [] and "No guides found" in r["message"] and "problem type" in r["message"]


# ---- US-16 Follow a guide step by step ----

def test_us16_checklist_source(client, make_staff):
    _, h = make_staff("noah")
    g = make(client, h).json()
    r = client.get(f"/api/guides/{g['id']}", headers=h).json()
    assert r["steps"] == MFA["steps"] and r["step_count"] == 7
    assert r["before_you_start"] == "Does the student have their new phone with them?"


# ---- US-17 Write and edit a guide ----

def test_us17_create(client, make_staff):
    _, h = make_staff("noah", display_name="Noah")
    r = make(client, h).json()
    assert r["created_by"] == "Noah" and r["created_at"] and r["problem_type"] == "mfa"


def test_us17_limits(client, make_staff, db):
    _, h = make_staff("noah")
    assert "title" in make(client, h, title=" ").text
    assert "at least one step" in make(client, h, steps=[" "]).text
    assert "20 steps at most" in make(client, h, steps=[f"s{i}" for i in range(21)]).text
    assert db.query(Guide).count() == 0


def test_us17_edit_shows_last_edited(client, make_staff):
    _, h = make_staff("noah", display_name="Noah")
    g = make(client, h).json()
    r = client.put(f"/api/guides/{g['id']}", json={**MFA, "steps": ["New step 1"] + MFA["steps"][1:]}, headers=h).json()
    assert r["steps"][0] == "New step 1" and r["edited_by"] == "Noah" and r["edited_at"]


def test_us17_reorder(client, make_staff):
    _, h = make_staff("noah")
    g = make(client, h, steps=["A", "B", "C", "D", "E"]).json()
    r = client.put(f"/api/guides/{g['id']}", json={**MFA, "steps": ["A", "D", "B", "C", "E"]}, headers=h).json()
    assert r["steps"] == ["A", "D", "B", "C", "E"]


# ---- US-18 Flag a guide as out of date ----

def test_us18_flag_reason_needed_clear_and_list(client, make_staff, freeze):
    freeze(2026, 10, 14, 10, 0)
    _, h = make_staff("noah", display_name="Noah")
    a = make(client, h, title="eduroam on Android 14", problem_type="wifi").json()
    b = make(client, h, title="Outlook on Mac", problem_type="email").json()
    assert "Say what's wrong" in client.post(f"/api/guides/{a['id']}/flag", json={"reason": ""}, headers=h).text
    flagged = client.post(f"/api/guides/{a['id']}/flag", json={"reason": "Android 15 menu changed"}, headers=h).json()
    assert flagged["flag"]["reason"] == "Android 15 menu changed" and flagged["flag"]["by"] == "Noah"
    freeze(2026, 10, 14, 11, 0)
    client.post(f"/api/guides/{b['id']}/flag", json={"reason": "New Outlook"}, headers=h)
    assert [g["id"] for g in client.get("/api/guides/needs-fixing", headers=h).json()] == [a["id"], b["id"]]
    cleared = client.post(f"/api/guides/{a['id']}/flag/fixed", headers=h).json()
    assert cleared["flag"] is None


# ---- US-19 Know when a guide was last checked ----

def test_us19_needs_review_and_senior_review(client, make_staff, freeze):
    freeze(2026, 6, 1, 10, 0)
    _, noah = make_staff("noah")
    _, lead = make_staff("nate", role=ROLE_LEAD, display_name="Nate")
    g = make(client, noah).json()
    assert g["needs_review"] is False
    freeze(2026, 10, 14, 10, 0)
    _, noah = make_staff("noah2")
    _, lead = make_staff("nate2", role=ROLE_LEAD, display_name="Nate")
    assert client.get(f"/api/guides/{g['id']}", headers=noah).json()["needs_review"] is True
    assert client.post(f"/api/guides/{g['id']}/reviewed", headers=noah).status_code == 403
    r = client.post(f"/api/guides/{g['id']}/reviewed", headers=lead).json()
    assert r["needs_review"] is False and r["reviewed_by"] == "Nate"


def test_guides_need_sign_in(client):
    assert client.get("/api/guides", params={"problem_type": "wifi"}).status_code == 401


# ---- Defects found while testing Product v2 (regression tests) ----

def test_us18_long_reason_is_refused_not_cut(client, make_staff):
    """D-P1: a flag reason over 300 characters was silently cut off, so the end of it was lost."""
    _, h = make_staff("noah")
    g = make(client, h).json()
    r = client.post(f"/api/guides/{g['id']}/flag", json={"reason": "x" * 301}, headers=h)
    assert r.status_code == 422 and "300" in r.text
    assert client.post(f"/api/guides/{g['id']}/flag", json={"reason": "x" * 300}, headers=h).status_code == 200


def test_us17_step_length_limit(client, make_staff):
    """D-P2: one step could be any length (a pasted email thread made the guide unreadable)."""
    _, h = make_staff("noah")
    r = make(client, h, steps=["x" * 501])
    assert r.status_code == 422 and "500" in r.text
    assert make(client, h, steps=["x" * 500]).status_code == 201


def test_us16_unknown_guide(client, make_staff):
    _, h = make_staff("noah")
    assert client.get("/api/guides/999", headers=h).status_code == 404
