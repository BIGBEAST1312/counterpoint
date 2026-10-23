# Database and live-update tests | Built by Mohit Sawant, owned by no feature
# AI disclosure: first version generated with Claude (Anthropic); reviewed and edited by the team.
"""Times go into the database as UTC and come back as UTC; live updates send only a topic, never data."""
import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.core import database
from app.core.database import UTCDateTime
from app.core.realtime import Hub


class _TestBase(DeclarativeBase):  # separate from the app's Base, so no test table reaches the real database
    pass


class Moment(_TestBase):
    __tablename__ = "moment"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(UTCDateTime)


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    _TestBase.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_times_come_back_as_utc(session):
    desk_time = datetime(2026, 10, 14, 12, 40, tzinfo=ZoneInfo("America/Regina"))
    session.add(Moment(at=desk_time))
    session.commit()
    stored = session.scalars(select(Moment.at)).one()
    assert stored == desk_time and stored.tzinfo == timezone.utc and stored.hour == 18


def test_time_without_a_zone_is_refused(session):
    session.add(Moment(at=datetime(2026, 10, 14, 12, 40)))
    with pytest.raises(StatementError):
        session.commit()


def test_feature_not_merged_yet_is_skipped(monkeypatch):
    monkeypatch.setattr(database, "FEATURES", database.FEATURES + ["notmergedyet"])
    assert database.import_feature("notmergedyet", "router") is None


class _FakeBrowser:
    def __init__(self, broken=False):
        self.sent, self.broken = [], broken

    async def send_json(self, message):
        if self.broken:
            raise RuntimeError("tab closed")
        self.sent.append(message)


def test_live_update_sends_only_the_topic():
    hub, tab, closed_tab = Hub(), _FakeBrowser(), _FakeBrowser(broken=True)
    hub.clients |= {tab, closed_tab}
    asyncio.run(hub.broadcast("queue"))
    assert tab.sent == [{"topic": "queue"}]
    assert closed_tab not in hub.clients


def test_unknown_topic_is_refused():
    with pytest.raises(AssertionError):
        asyncio.run(Hub().broadcast("not-a-topic"))
