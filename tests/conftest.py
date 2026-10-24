# Shared test setup | Built by Mohit Sawant, owned by no feature
# AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the team.
"""Every test gets a fresh in-memory database, so tests never touch real desk data and can run
in any order. `freeze` sets the clock so time-based rules (missed calls, opening hours) are testable."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.models import ROLE_ASSISTANT, Staff
from app.auth.security import hash_password
from app.core import clock, config
from app.core.config import LOCAL_TZ
from app.core.database import get_db, init_db
from app.main import app

PASSWORD = "test-pass-123"


@pytest.fixture(autouse=True)
def no_real_email(monkeypatch):
    """Tests never send real email, even if a .env file sets up a mail server.
    The email tests switch it on themselves with a fake server."""
    monkeypatch.setattr(config, "SMTP_HOST", "")


@pytest.fixture
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = Session()

    def override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    yield session
    session.close()
    app.dependency_overrides.clear()


@pytest.fixture
def client(db):
    return TestClient(app)  # no `with` block: skips startup, so the real database file is never created


@pytest.fixture
def freeze(monkeypatch):
    """freeze(2026, 10, 14, 12, 40) sets 'now' to that LOCAL desk time. Call again to move time."""
    def _freeze(*args) -> datetime:
        moment = datetime(*args, tzinfo=LOCAL_TZ).astimezone(timezone.utc)
        monkeypatch.setattr(clock, "utcnow", lambda: moment)
        return moment
    return _freeze


@pytest.fixture
def make_staff(db, client):
    """make_staff("sam") -> (Staff, headers) with a real sign-in token.
    If a test freezes the clock, call freeze() first: sign-ins expire 12 hours after they start."""
    def _make(username="sam", role=ROLE_ASSISTANT, display_name=None, email=None):
        staff = Staff(username=username, display_name=display_name or username.title(), email=email,
                      password_hash=hash_password(PASSWORD), role=role)
        db.add(staff)
        db.commit()
        token = client.post("/api/auth/login", json={"username": username, "password": PASSWORD}).json()["token"]
        return staff, {"Authorization": f"Bearer {token}"}
    return _make
