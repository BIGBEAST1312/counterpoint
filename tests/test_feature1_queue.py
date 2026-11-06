# Feature 1 · Walk-up queue | Owner: Mohit Sawant
# AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the owner.
"""One test per acceptance test in US-01 to US-06."""
from datetime import timedelta

from sqlalchemy import update

from app.core import clock
from app.queue import logic
from app.queue.models import CALLED, DONE, WAITING, Visit


def check_in(client, name="Jane", ptype="mfa"):
    return client.post("/api/visits", json={"first_name": name, "problem_type": ptype})


def add(db, n, status=WAITING, minutes_ago=0, **kw):
    now = clock.utcnow()
    v = Visit(ticket_date=clock.local_date(now), ticket_no=n, first_name="Student",
              problem_type="wifi", status=status, arrived_at=now - timedelta(minutes=minutes_ago), **kw)
    db.add(v)
    db.commit()
    return v


def recent_done(db, n, counter, length=10):
    """A finished visit `length` minutes long, called a few minutes ago at `counter`."""
    now = clock.utcnow()
    called = now - timedelta(minutes=length + 2)
    return add(db, n, status=DONE, minutes_ago=length + 5, counter=counter, called_at=called,
               served_at=called, finished_at=called + timedelta(minutes=length))


# ---- US-01 Check in at the kiosk ----

def test_us01_happy_path(client, freeze):
    freeze(2026, 10, 14, 10, 0)
    r = check_in(client)
    assert r.status_code == 201
    assert r.json()["ticket"] == "#001" and r.json()["place"] == 1


def test_us01_numbering_restarts_next_day(client, freeze):
    freeze(2026, 10, 14, 10, 0)
    check_in(client)
    assert check_in(client, "Omar").json()["ticket"] == "#002"
    freeze(2026, 10, 15, 10, 0)
    assert check_in(client, "Li").json()["ticket"] == "#001"


def test_us01_missing_information(client, db):
    assert check_in(client, name="  ").status_code == 422
    r = check_in(client, ptype="")
    assert r.status_code == 422 and "what you need help with" in r.text
    assert db.query(Visit).count() == 0


def test_us01_first_name_only(client, db):
    for bad in ("abc123", "11223344"):
        r = check_in(client, name=bad)
        assert r.status_code == 422 and "first name only" in r.text
    assert db.query(Visit).count() == 0


# ---- US-02 See my estimated wait ----

def test_us02_estimate_with_two_counters(client, db, freeze):
    freeze(2026, 10, 14, 12, 0)
    recent_done(db, 1, "Counter 1")
    recent_done(db, 2, "Counter 2")
    for n in range(3, 7):
        add(db, n, minutes_ago=10 - n)
    r = check_in(client).json()
    assert r["place"] == 5 and r["estimate_minutes"] == 20 and r["message"] == "About 20 minutes."


def test_us02_one_counter_calling(client, db, freeze):
    freeze(2026, 10, 14, 12, 0)
    recent_done(db, 1, "Counter 1")
    recent_done(db, 2, "Counter 1")
    for n in range(3, 7):
        add(db, n)
    assert check_in(client).json()["estimate_minutes"] == 40


def test_us02_default_rate_when_no_visits_finished(client, db, freeze):
    freeze(2026, 10, 14, 12, 0)
    add(db, 1, status=CALLED, counter="Counter 1", called_at=clock.utcnow())   # calling, but nothing finished
    add(db, 2)
    add(db, 3)
    assert check_in(client).json()["estimate_minutes"] == 20   # 2 ahead x 10 default / 1 counter


def test_us02_no_recent_calls(client, db, freeze):
    freeze(2026, 10, 14, 12, 0)
    add(db, 1)
    r = check_in(client)
    assert r.status_code == 201
    assert r.json()["estimate_minutes"] is None and "can't be estimated" in r.json()["message"]


# ---- US-03 Leave the line myself ----

def test_us03_leave(client, db):
    for name in ("Ann", "Ben", "Jane", "Kai"):
        check_in(client, name)
    assert client.post("/api/visits/leave", json={"ticket_no": 3, "first_name": "jane"}).status_code == 200
    assert client.get("/api/visits/place", params={"ticket_no": 4}).json()["place"] == 3


def test_us03_wrong_details(client):
    check_in(client, "Jane")
    r = client.post("/api/visits/leave", json={"ticket_no": 1, "first_name": "Bob"})
    assert r.status_code == 404 and "wasn't found" in r.text


def test_us03_already_called(client, make_staff):
    check_in(client, "Jane")
    _, h = make_staff()
    client.post("/api/queue/call-next", json={"counter": "Counter 1"}, headers=h)
    r = client.post("/api/visits/leave", json={"ticket_no": 1, "first_name": "Jane"})
    assert r.status_code == 409 and "already been called" in r.text


# ---- US-04 Called in arrival order ----

def test_us04_longest_wait_first(client, make_staff):
    _, h = make_staff()
    for name in ("Ann", "Ben", "Cy", "Jane", "Kai"):
        check_in(client, name)
    for _ in range(3):
        client.post("/api/queue/call-next", json={"counter": "Counter 1"}, headers=h)
    r = client.post("/api/queue/call-next", json={"counter": "Counter 1"}, headers=h)
    assert r.json()["ticket"] == "#004" and r.json()["first_name"] == "Jane"


def test_us04_only_real_counters(client, make_staff, db):
    _, h = make_staff()
    check_in(client)
    r = client.post("/api/queue/call-next", json={"counter": "Counter 3"}, headers=h)
    assert r.status_code == 422
    assert db.query(Visit).one().status == WAITING


def test_us04_never_called_twice(client, make_staff, db):
    _, h = make_staff()
    check_in(client, "Jane")
    first = client.post("/api/queue/call-next", json={"counter": "Counter 1"}, headers=h)
    second = client.post("/api/queue/call-next", json={"counter": "Counter 2"}, headers=h)
    assert first.status_code == 200 and second.status_code == 409 and "Nobody is waiting" in second.text
    # The race itself: a second conditional UPDATE on the same visit changes nothing.
    visit = db.query(Visit).one()
    result = db.execute(update(Visit).where(Visit.id == visit.id, Visit.status == WAITING).values(counter="Counter 2"))
    assert result.rowcount == 0


def test_us04_my_place_moves_up(client, make_staff):
    _, h = make_staff()
    for name in ("Ann", "Ben", "Jane"):
        check_in(client, name)
    assert client.get("/api/visits/place", params={"ticket_no": 3}).json()["place"] == 3
    client.post("/api/queue/call-next", json={"counter": "Counter 1"}, headers=h)
    assert client.get("/api/visits/place", params={"ticket_no": 3}).json()["place"] == 2


def test_counter_panel_needs_sign_in(client):
    assert client.post("/api/queue/call-next", json={"counter": "Counter 1"}).status_code == 401


# ---- US-05 See when it's my turn ----

def test_us05_lobby_shows_my_call(client, make_staff):
    _, h = make_staff()
    for name in ("Ann", "Ben", "Cy", "Jane"):
        check_in(client, name)
    for _ in range(4):
        client.post("/api/queue/call-next", json={"counter": "Counter 1"}, headers=h)
    top = client.get("/api/lobby").json()[0]
    assert top == {"ticket": "#004", "counter": "Counter 1", "missed": False}


def test_us05_ticket_and_counter_only(client, make_staff):
    _, h = make_staff()
    check_in(client, "Jane", "mfa")
    client.post("/api/queue/call-next", json={"counter": "Counter 1"}, headers=h)
    r = client.get("/api/lobby")
    assert "Jane" not in r.text and "mfa" not in r.text
    assert set(r.json()[0]) == {"ticket", "counter", "missed"}


def test_us05_three_recent_calls_newest_first(client, make_staff, freeze):
    freeze(2026, 10, 14, 10, 0)
    _, h = make_staff()
    for name in ("A", "B", "C", "D", "E"):
        check_in(client, name)
    for minute in range(1, 6):
        freeze(2026, 10, 14, 10, minute)
        r = client.post("/api/queue/call-next", json={"counter": "Counter 1"}, headers=h)
        client.post(f"/api/visits/{r.json()['id']}/here", headers=h)
    assert [c["ticket"] for c in client.get("/api/lobby").json()] == ["#005", "#004", "#003"]


# ---- US-06 Free my place when I'm done ----

def test_us06_done_frees_the_counter(client, make_staff, db):
    _, h = make_staff()
    check_in(client, "Jane")
    v = client.post("/api/queue/call-next", json={"counter": "Counter 1"}, headers=h).json()
    client.post(f"/api/visits/{v['id']}/here", headers=h)
    r = client.post(f"/api/visits/{v['id']}/done", headers=h)
    assert r.json()["status"] == "done"
    assert db.query(Visit).one().finished_at is not None
    assert client.get("/api/queue", headers=h).json()["at_counters"] == []


def test_us06_missed_call_after_five_minutes(client, make_staff, freeze):
    freeze(2026, 10, 14, 11, 0)
    _, h = make_staff()
    for _ in range(9):
        check_in(client, "Student")
    for _ in range(9):
        client.post("/api/queue/call-next", json={"counter": "Counter 2"}, headers=h)
    freeze(2026, 10, 14, 11, 4)
    assert client.get("/api/lobby").json()[0]["missed"] is False
    freeze(2026, 10, 14, 11, 5)
    lobby = client.get("/api/lobby").json()
    assert lobby[0]["missed"] is True
    queue = client.get("/api/queue", headers=h).json()
    assert queue["at_counters"] == []


def test_us06_done_feeds_the_service_rate(client, make_staff, db, freeze):
    freeze(2026, 10, 14, 10, 0)
    _, h = make_staff()
    check_in(client, "Jane")
    v = client.post("/api/queue/call-next", json={"counter": "Counter 1"}, headers=h).json()
    client.post(f"/api/visits/{v['id']}/here", headers=h)
    freeze(2026, 10, 14, 10, 16)
    client.post(f"/api/visits/{v['id']}/done", headers=h)
    assert logic.service_rate(db, clock.utcnow()) == 16
    assert "rate" not in client.get("/api/queue/summary").text


# ---- Defects found while testing Product v2 (regression tests) ----

def test_us06_done_without_here_counts_from_the_call(client, make_staff, db, freeze):
    """D-M1: pressing Done without pressing Here first used to record a 0-minute visit,
    which pulled the service rate down and made US-02's estimate too short."""
    freeze(2026, 10, 14, 10, 0)
    _, h = make_staff()
    check_in(client, "Jane")
    v = client.post("/api/queue/call-next", json={"counter": "Counter 1"}, headers=h).json()
    freeze(2026, 10, 14, 10, 4)
    client.post(f"/api/visits/{v['id']}/done", headers=h)
    assert logic.service_rate(db, clock.utcnow()) == 4
