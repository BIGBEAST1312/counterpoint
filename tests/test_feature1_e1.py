# Feature 1 (E1): one test per acceptance test in US-01 to US-03 | Owner: Mohit Sawant
from datetime import timedelta

from app.core import clock
from app.queue.models import CALLED, DONE, WAITING, Visit


def check_in(client, name="Jane", ptype="mfa"):
    return client.post("/api/visits", json={"first_name": name, "problem_type": ptype})


def add(db, n, status=WAITING, **kw):
    now = clock.utcnow()
    v = Visit(ticket_date=clock.local_date(now), ticket_no=n, first_name="Student", problem_type="wifi",
              status=status, arrived_at=now, **kw)
    db.add(v)
    db.commit()
    return v


def finished(db, n, counter, length=10):
    """A visit that lasted `length` minutes, called a few minutes ago at `counter`."""
    called = clock.utcnow() - timedelta(minutes=length + 2)
    return add(db, n, status=DONE, counter=counter, called_at=called, served_at=called,
               finished_at=called + timedelta(minutes=length))


# ---- US-01 Check in at the kiosk ----

def test_us01_ticket_and_place(client, freeze):
    freeze(2026, 10, 14, 10, 0)
    r = check_in(client)
    assert r.status_code == 201
    assert r.json()["ticket"] == "#001" and r.json()["place"] == 1


def test_us01_numbers_restart_each_day(client, freeze):
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

def test_us02_two_counters(client, db, freeze):
    freeze(2026, 10, 14, 12, 0)
    finished(db, 1, "Counter 1")
    finished(db, 2, "Counter 2")
    for n in range(3, 7):
        add(db, n)
    r = check_in(client).json()
    assert r["place"] == 5 and r["estimate_minutes"] == 20 and r["message"] == "About 20 minutes."


def test_us02_one_counter(client, db, freeze):
    freeze(2026, 10, 14, 12, 0)
    finished(db, 1, "Counter 1")
    finished(db, 2, "Counter 1")
    for n in range(3, 7):
        add(db, n)
    assert check_in(client).json()["estimate_minutes"] == 40


def test_us02_default_length_when_nothing_finished(client, db, freeze):
    freeze(2026, 10, 14, 12, 0)
    add(db, 1, status=CALLED, counter="Counter 1", called_at=clock.utcnow())
    add(db, 2)
    add(db, 3)
    assert check_in(client).json()["estimate_minutes"] == 20   # 2 ahead x 10 min / 1 counter


def test_us02_no_counter_has_called(client, db, freeze):
    freeze(2026, 10, 14, 12, 0)
    add(db, 1)
    r = check_in(client)
    assert r.status_code == 201
    assert r.json()["estimate_minutes"] is None and "can't be estimated" in r.json()["message"]


# ---- US-03 Leave the line myself ----

def test_us03_leave_and_others_move_up(client):
    for name in ("Ann", "Ben", "Jane", "Kai"):
        check_in(client, name)
    assert client.post("/api/visits/leave", json={"ticket_no": 3, "first_name": "jane"}).status_code == 200
    assert client.get("/api/visits/place", params={"ticket_no": 4}).json()["place"] == 3


def test_us03_wrong_details(client):
    check_in(client, "Jane")
    r = client.post("/api/visits/leave", json={"ticket_no": 1, "first_name": "Bob"})
    assert r.status_code == 404 and "wasn't found" in r.text


def test_us03_already_called(client, db):
    check_in(client, "Jane")
    v = db.query(Visit).one()
    v.status = CALLED
    db.commit()
    r = client.post("/api/visits/leave", json={"ticket_no": 1, "first_name": "Jane"})
    assert r.status_code == 409 and "already been called" in r.text
