# Shared infrastructure tests | Built by Mohit Sawant, owned by no feature
# AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the team.
"""Sign-in, sessions and the shared settings. These run even before any feature is merged."""
from app.auth.models import ROLE_SUPERVISOR
from app.core import clock


def test_health_and_settings_are_public(client):
    assert client.get("/api/health").status_code == 200
    s = client.get("/api/settings").json()
    assert s["counters"] == ["Counter 1", "Counter 2"] and any(p["key"] == "wifi" for p in s["problem_types"])


def test_sign_in_and_me(client, make_staff):
    _, h = make_staff("nate", display_name="Nate")
    me = client.get("/api/auth/me", headers=h).json()
    assert me["username"] == "nate" and me["display_name"] == "Nate"


def test_wrong_password_same_message_as_unknown_user(client, make_staff):
    make_staff("nate")
    wrong = client.post("/api/auth/login", json={"username": "nate", "password": "nope-nope"})
    unknown = client.post("/api/auth/login", json={"username": "ghost", "password": "nope-nope"})
    assert wrong.status_code == unknown.status_code == 401 and wrong.json() == unknown.json()


def test_sign_out_ends_the_session(client, make_staff):
    _, h = make_staff("nate")
    client.post("/api/auth/logout", headers=h)
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_session_expires_after_12_hours(client, make_staff, freeze, monkeypatch):
    start = freeze(2026, 10, 14, 9, 0)
    _, h = make_staff("nate")
    from datetime import timedelta
    monkeypatch.setattr(clock, "utcnow", lambda: start + timedelta(hours=12, minutes=1))
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_only_supervisors_create_staff(client, make_staff):
    _, assistant = make_staff("nate")
    _, boss = make_staff("chewy", role=ROLE_SUPERVISOR)
    new = {"username": "Oliver", "display_name": "Oliver", "password": "long-enough-1", "role": "assistant"}
    assert client.post("/api/staff", json=new, headers=assistant).status_code == 403
    r = client.post("/api/staff", json=new, headers=boss)
    assert r.status_code == 201 and r.json()["username"] == "oliver"
    assert client.post("/api/staff", json=new, headers=boss).status_code == 409
