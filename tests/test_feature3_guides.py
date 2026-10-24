# Feature 3 · Fix guides | Owner: Priyesh Patel
# AI disclosure: Used AI for concept explanations, understanding syntax and debugging guidance.
"""One test per acceptance test in US-14 to US-16 (Product v1). US-17 to US-19 come in Product v2.

Writing guides in the app arrives with US-17, so these tests add guides straight to the database,
the same way scripts/seed_demo.py does. (US-16's tick boxes live in the browser; the API test checks
the numbered steps and 'before you start' they are built from.)"""
from app.core import clock
from app.guides.models import Guide, GuideFlag, GuideStep

MFA = {"title": "MFA: re-register a new phone", "problem_type": "mfa",
       "before_you_start": "Does the student have their new phone with them?",
       "steps": [f"Step {i}" for i in range(1, 8)]}


def make(db, author, **kw) -> Guide:
    """Save a guide written by `author` (a Staff row)."""
    g = {**MFA, **kw}
    now = clock.utcnow()
    guide = Guide(title=g["title"], problem_type=g["problem_type"], before_you_start=g["before_you_start"],
                  created_by_id=author.id, created_at=now, reviewed_at=now)
    guide.steps = [GuideStep(position=i, text=t) for i, t in enumerate(g["steps"], 1)]
    db.add(guide)
    db.commit()
    return guide


# ---- US-14 Browse guides by problem type ----

def test_us14_by_type_alphabetical(client, db, make_staff):
    noah, h = make_staff("noah")
    make(db, noah, title="eduroam on Android 14", problem_type="wifi")
    make(db, noah, title="Connect a Mac to eduroam", problem_type="wifi")
    make(db, noah)  # an MFA guide, not shown
    r = client.get("/api/guides", params={"problem_type": "wifi"}, headers=h).json()
    assert [g["title"] for g in r["guides"]] == ["Connect a Mac to eduroam", "eduroam on Android 14"]
    assert all(g["reviewed_at"] for g in r["guides"])


def test_us14_empty_type(client, make_staff):
    _, h = make_staff("noah")
    assert client.get("/api/guides", params={"problem_type": "printing"}, headers=h).json()["message"] == "No guides for this yet."


def test_us14_flagged_guides_stand_out(client, db, make_staff):
    noah, h = make_staff("noah")
    flagged = make(db, noah, title="eduroam on Android 14", problem_type="wifi")
    make(db, noah, title="Connect a Mac to eduroam", problem_type="wifi")
    # Flagging arrives with US-18, so the flag is added directly.
    db.add(GuideFlag(guide_id=flagged.id, reason="Android 15 menu changed", flagged_by_id=noah.id, flagged_at=clock.utcnow()))
    db.commit()
    rows = client.get("/api/guides", params={"problem_type": "wifi"}, headers=h).json()["guides"]
    assert {g["title"]: g["flagged"] for g in rows} == {"Connect a Mac to eduroam": False, "eduroam on Android 14": True}


# ---- US-15 Search guides ----

def test_us15_keyword(client, db, make_staff):
    noah, h = make_staff("noah")
    make(db, noah, title="eduroam on Android 14", problem_type="wifi")
    make(db, noah)
    titles = [g["title"] for g in client.get("/api/guides/search", params={"q": "android wifi"}, headers=h).json()["guides"]]
    assert titles == ["eduroam on Android 14"]


def test_us15_title_matches_first(client, db, make_staff):
    noah, h = make_staff("noah")
    make(db, noah, title="Outlook keeps asking for a password", problem_type="email", steps=["Clear cached credentials"])
    make(db, noah, title="Reset a password", problem_type="password", steps=["Use the reset page"])
    make(db, noah, title="Set up Outlook on a Mac", problem_type="email", steps=["Sign in with your password"])
    titles = [g["title"] for g in client.get("/api/guides/search", params={"q": "password"}, headers=h).json()["guides"]]
    assert titles[-1] == "Set up Outlook on a Mac"   # only matched in its steps


def test_us15_no_results(client, make_staff):
    _, h = make_staff("noah")
    r = client.get("/api/guides/search", params={"q": "fax machine"}, headers=h).json()
    assert r["guides"] == [] and "No guides found" in r["message"] and "problem type" in r["message"]


# ---- US-16 Follow a guide step by step ----

def test_us16_checklist_source(client, db, make_staff):
    noah, h = make_staff("noah")
    g = make(db, noah)
    r = client.get(f"/api/guides/{g.id}", headers=h).json()
    assert r["steps"] == MFA["steps"] and r["step_count"] == 7
    assert r["before_you_start"] == "Does the student have their new phone with them?"


def test_us16_unknown_guide(client, make_staff):
    _, h = make_staff("noah")
    assert client.get("/api/guides/999", headers=h).status_code == 404


def test_guides_need_sign_in(client):
    assert client.get("/api/guides", params={"problem_type": "wifi"}).status_code == 401
